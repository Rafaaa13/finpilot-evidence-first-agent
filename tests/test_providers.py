from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from finpilot.data_sources import (
    ProviderDependencyError,
    ProviderNetworkError,
    ProviderPolicyError,
    ProviderValidationError,
    SecEdgarProvider,
    SourcePolicy,
    UserSnapshotProvider,
    YFinanceProvider,
    data_doctor,
)
from finpilot.investment import demo_inputs


from finpilot.cli import main


def price_frame(values=(100.0, 101.0), dates=("2024-01-02", "2024-01-03")):
    return pd.DataFrame({"Adj Close": list(values)}, index=pd.to_datetime(list(dates)))


def companyfacts():
    # Fabricated protocol data, not an SEC or real-company numeric snapshot.
    return {"cik": 123, "facts": {"us-gaap": {"Revenue": {"units": {"USD": [
        {"val": 100, "accn": "0000000001-24-000001", "filed": "2024-02-01",
         "start": "2023-01-01", "end": "2023-12-31"}
    ]}}}}}


class FakeYFinance:
    __version__ = "fake-test"

    def __init__(self, frame=None, error=None):
        self.frame = frame
        self.error = error
        self.calls = []

    def download(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error:
            raise self.error
        return self.frame


class FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes, url: str):
        super().__init__(payload)
        self.url = url

    def geturl(self):
        return self.url


class ProviderTests(unittest.TestCase):
    def test_import_and_doctor_do_not_import_yfinance_or_call_network(self):
        with patch("finpilot.data_sources.importlib.import_module") as importer:
            result = data_doctor(provider="yfinance")
            importer.assert_not_called()
        self.assertFalse(result["network_called"])
        self.assertFalse(result["cache_written"])
        self.assertFalse(result["synthetic_fallback"])

    def test_network_requires_two_explicit_policy_opt_ins(self):
        fake = FakeYFinance(pd.DataFrame())
        provider = YFinanceProvider(yf_module=fake)
        with self.assertRaises(ProviderPolicyError):
            provider.fetch("AAPL", "2024-01-01", "2024-01-05")
        self.assertEqual(fake.calls, [])

    def test_missing_optional_dependency_is_actionable_and_lazy(self):
        provider = YFinanceProvider(
            policy=SourcePolicy(allow_network=True, accept_terms=True)
        )
        with patch("finpilot.data_sources.importlib.import_module", side_effect=ImportError("absent")) as importer:
            with self.assertRaisesRegex(ProviderDependencyError, "yfinance unavailable"):
                provider.fetch("AAPL", "2024-01-01", "2024-01-05")
        importer.assert_called_once_with("yfinance")

    def test_yfinance_failure_does_not_silently_use_fixture(self):
        fake = FakeYFinance(error=TimeoutError("offline fake"))
        provider = YFinanceProvider(
            SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake
        )
        with self.assertRaises(ProviderNetworkError):
            provider.fetch("AAPL", "2024-01-01", "2024-01-05")
        self.assertEqual(len(fake.calls), 1)

    def test_yfinance_result_has_provenance_and_is_not_verified(self):
        dates = pd.to_datetime(["2024-01-02", "2024-01-03"])
        frame = pd.DataFrame(
            {"Adj Close": [100.0, 101.0], "Close": [99.0, 100.0]}, index=dates
        )
        fake = FakeYFinance(frame=frame)
        result = YFinanceProvider(
            SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake
        ).fetch("aapl", "2024-01-01", "2024-01-03")
        self.assertEqual(result.data_kind, "real_user_fetch")
        self.assertFalse(result.verified)
        output = result.to_dict()
        self.assertEqual(output["verification_status"], "not_independently_verified")
        self.assertEqual(output["record_count"], 2)
        self.assertEqual(output["records"][0]["date"], "2024-01-02")
        self.assertEqual(output["provenance"]["request"]["provider_end_exclusive"], "2024-01-04")
        self.assertEqual(fake.calls[0][0], ("AAPL",))
        self.assertEqual(fake.calls[0][1]["auto_adjust"], False)
        self.assertNotIn("api_key", output["provenance"])

    def test_yfinance_requires_adj_close_and_does_not_substitute_close(self):
        dates = pd.to_datetime(["2024-01-02"])
        fake = FakeYFinance(pd.DataFrame({"Close": [100.0]}, index=dates))
        with self.assertRaisesRegex(ProviderValidationError, "Adj Close"):
            YFinanceProvider(
                SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake
            ).fetch("AAPL", "2024-01-01", "2024-01-03")

    def test_sec_wrapper_uses_injected_http_and_raw_fact_provenance(self):
        url = "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000123.json"
        payload = {
            "cik": "0000000123",
            "facts": {
                "us-gaap": {
                    "Revenue": {
                        "label": "Revenue",
                        "units": {
                            "USD": [{
                                "val": 100,
                                "accn": "0000000001-24-000001",
                                "filed": "2024-02-01",
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                            }]
                        },
                    }
                }
            },
        }
        calls = []

        def opener(request, timeout):
            calls.append((request, timeout))
            return FakeResponse(json.dumps(payload).encode(), url)

        result = SecEdgarProvider(
            SourcePolicy(
                allow_network=True,
                accept_terms=True,
                user_agent="FinPilot Test contact@finpilot.invalid",
            ),
            cik="123",
            opener=opener,
        ).fetch("AAPL", "2024-01-01", "2024-12-31")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.data_kind, "real_user_fetch")
        self.assertFalse(result.verified)
        self.assertEqual(result.provenance["cik"], "0000000123")
        self.assertEqual(result.records[0]["record_type"], "sec_raw_fact")
        self.assertEqual(result.records[0]["raw_fact"]["filed"], "2024-02-01")
        self.assertEqual(result.to_dict()["verification_status"], "not_independently_verified")

    def test_sec_does_not_guess_ticker_to_cik(self):
        policy = SourcePolicy(
            allow_network=True, accept_terms=True, user_agent="FinPilot Test contact@finpilot.invalid"
        )
        with self.assertRaisesRegex(ProviderValidationError, "explicit.*CIK"):
            SecEdgarProvider(policy).fetch("AAPL", "2024-01-01", "2024-01-02")

    def test_date_bounds_are_validated_before_provider_call(self):
        fake = FakeYFinance(pd.DataFrame())
        provider = YFinanceProvider(
            SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake
        )
        with self.assertRaises(ProviderValidationError):
            provider.fetch("AAPL", "2024-01-05", "2024-01-01")
        with self.assertRaises(ProviderValidationError):
            provider.fetch("AAPL", "2024-01-01", "2999-01-01")
        self.assertEqual(fake.calls, [])

    def test_local_snapshot_is_explicitly_unverified_and_uses_existing_contract(self):
        inputs = demo_inputs()
        result = UserSnapshotProvider().load(
            inputs["stocks_csv"], inputs["prices_csv"], inputs["as_of"]
        )
        self.assertEqual(result.data_kind, "synthetic")
        self.assertFalse(result.verified)
        self.assertEqual(result.to_dict()["verification_status"], "not_independently_verified")
        self.assertTrue(result.provenance["input_hash"])
        self.assertGreater(result.record_count, 0)


    def test_module_import_is_independent_of_optional_libraries(self):
        # Fresh process ensures previously imported test modules cannot hide eager imports.
        script = '''import sys, importlib.abc
class BlockOptional(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in {'yfinance', 'pandas', 'numpy'}:
            raise AssertionError('eager optional import: ' + name)
sys.meta_path.insert(0, BlockOptional())
import finpilot.data_sources as d
d.YFinanceProvider()
d.SecEdgarProvider()
assert 'yfinance' not in sys.modules
'''
        completed = subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[1],
                                   env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
                                   capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_terms_opt_in_precedes_import_or_network(self):
        with patch("finpilot.data_sources.importlib.import_module") as importer:
            with self.assertRaisesRegex(ProviderPolicyError, "terms"):
                YFinanceProvider(SourcePolicy(allow_network=True)).fetch("AAPL", "2024-01-01", "2024-01-03")
            importer.assert_not_called()

    def test_policy_rejects_ambiguous_or_unbounded_values(self):
        for kwargs in ({"allow_network": 1}, {"accept_terms": "yes"}, {"max_days": True},
                       {"max_records": 1.5}, {"max_response_bytes": -1}, {"timeout_seconds": float("nan")},
                       {"user_agent": "test\r\nInjected: secret"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ProviderValidationError):
                SourcePolicy(**kwargs)

    def test_yfinance_validation_never_fills_or_truncates_bad_rows(self):
        bad_frames = [
            price_frame(values=(100, float("nan"))), price_frame(values=(0, 1)),
            price_frame(values=(100, float("inf"))), price_frame(values=(100, True)),
            price_frame(dates=("2024-01-02", "2024-01-02")),
            price_frame(dates=("2023-12-31", "2024-01-03")),
            pd.DataFrame(),
        ]
        for frame in bad_frames:
            fake = FakeYFinance(frame)
            with self.subTest(frame=frame), self.assertRaises(ProviderValidationError):
                YFinanceProvider(SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake).fetch(
                    "AAPL", "2024-01-01", "2024-01-03")
            self.assertEqual(len(fake.calls), 1)

    def test_yfinance_supports_single_ticker_multiindex_without_synthetic_identity(self):
        frame = price_frame()
        frame.columns = pd.MultiIndex.from_tuples([("Adj Close", "AAPL")])
        result = YFinanceProvider(SourcePolicy(allow_network=True, accept_terms=True), yf_module=FakeYFinance(frame)).fetch(
            "AAPL", "2024-01-01", "2024-01-03")
        self.assertEqual({r["symbol"] for r in result.records}, {"AAPL"})
        self.assertTrue(result.prices_csv().startswith("date,symbol,adj_close\n"))
        self.assertTrue(result.provenance["normalized_hash"].startswith("sha256:"))
        self.assertEqual(result.provenance["provider_version"], "fake-test")
        self.assertIn("fetched_at", result.provenance)
        self.assertEqual(len(result.provenance["normalized_hash"]), 71)
        json.dumps(result.to_dict(), allow_nan=False)

    def test_yfinance_record_limit_and_symbol_rejection_before_fetch(self):
        fake = FakeYFinance(price_frame())
        policy = SourcePolicy(allow_network=True, accept_terms=True, max_records=1)
        with self.assertRaisesRegex(ProviderValidationError, "max_records"):
            YFinanceProvider(policy, yf_module=fake).fetch("AAPL", "2024-01-01", "2024-01-03")
        fake.calls.clear()
        for symbol in ("", "../AAPL", "AAPL;echo", " AAPL", "AAPL/TEST", "ß", "ı"):
            with self.assertRaises(ProviderValidationError):
                YFinanceProvider(policy, yf_module=fake).fetch(symbol, "2024-01-01", "2024-01-03")
        self.assertFalse(fake.calls)

    def test_provider_error_text_does_not_leak_secrets(self):
        fake = FakeYFinance(error=RuntimeError("api_key=TOP_SECRET"))
        with self.assertRaises(ProviderNetworkError) as error:
            YFinanceProvider(SourcePolicy(allow_network=True, accept_terms=True), yf_module=fake).fetch(
                "AAPL", "2024-01-01", "2024-01-03")
        self.assertNotIn("TOP_SECRET", str(error.exception))

    def test_sec_policy_requires_real_user_agent_before_http(self):
        for agent in (None, "test", "FinPilot research@example.com"):
            with patch("urllib.request.urlopen") as network:
                with self.assertRaises(ProviderPolicyError):
                    SecEdgarProvider(SourcePolicy(allow_network=True, accept_terms=True, user_agent=agent), cik="123").fetch(
                        "AAPL", "2024-01-01", "2024-12-31")
                network.assert_not_called()

    def test_sec_bounded_fake_http_does_not_cache_contact_information(self):
        calls = []
        def opener(request, timeout):
            calls.append(request)
            return FakeResponse(json.dumps(companyfacts()).encode(), request.full_url)
        with tempfile.TemporaryDirectory() as folder:
            result = SecEdgarProvider(SourcePolicy(allow_network=True, accept_terms=True,
                                     user_agent="Research private-contact@finpilot.invalid"), cik="123", opener=opener).fetch(
                                     "AAPL", "2024-01-01", "2024-12-31")
            self.assertEqual(list(Path(folder).iterdir()), [])
        self.assertEqual(calls[0].get_header("Accept-encoding"), "identity")
        serialized = json.dumps(result.to_dict(), allow_nan=False)
        self.assertNotIn("private-contact", serialized)
        self.assertNotIn("User-Agent", serialized)
        self.assertTrue(result.provenance["raw_response_hash"].startswith("sha256:"))
        with self.assertRaises(ProviderValidationError):
            result.prices_csv()

    def test_sec_network_failure_and_size_limit_are_explicit_no_fallback(self):
        policy = SourcePolicy(allow_network=True, accept_terms=True, user_agent="Research contact@finpilot.invalid")
        def fail(request, timeout):
            raise urllib.error.URLError("token=TOP_SECRET")
        with self.assertRaises(ProviderNetworkError) as error:
            SecEdgarProvider(policy, cik="123", opener=fail).fetch("AAPL", "2024-01-01", "2024-12-31")
        self.assertNotIn("TOP_SECRET", str(error.exception))
        def large(request, timeout):
            return FakeResponse(b"x" * 11, request.full_url)
        bounded = SourcePolicy(allow_network=True, accept_terms=True, user_agent="Research contact@finpilot.invalid", max_response_bytes=10)
        with self.assertRaisesRegex(ProviderNetworkError, "max_response_bytes"):
            SecEdgarProvider(bounded, cik="123", opener=large).fetch("AAPL", "2024-01-01", "2024-12-31")

    def test_sec_filters_by_filed_date_not_period_end_and_retains_accession(self):
        data = companyfacts()
        rows = data["facts"]["us-gaap"]["Revenue"]["units"]["USD"]
        rows.append({**rows[0], "filed": "2025-01-01", "val": 200})
        def opener(request, timeout):
            return FakeResponse(json.dumps(data).encode(), request.full_url)
        result = SecEdgarProvider(SourcePolicy(allow_network=True, accept_terms=True,
                                 user_agent="Research contact@finpilot.invalid"), cik="123", opener=opener).fetch(
                                 "AAPL", "2024-01-01", "2024-12-31")
        self.assertEqual(result.record_count, 1)
        self.assertEqual(result.records[0]["raw_fact"]["accn"], "0000000001-24-000001")
        self.assertIn("filed", result.provenance["date_bounds_semantics"])

    def test_sec_rejects_nonjson_wrong_company_invalid_fact_and_redirect(self):
        base = companyfacts()
        wrong_cik = {**base, "cik": 456}
        invalid = companyfacts()
        invalid["facts"]["us-gaap"]["Revenue"]["units"]["USD"][0]["val"] = "100"
        for payload in (b"not-json", json.dumps(wrong_cik).encode(), json.dumps(invalid).encode()):
            def opener(request, timeout, raw=payload):
                return FakeResponse(raw, request.full_url)
            with self.assertRaises(ProviderValidationError):
                SecEdgarProvider(SourcePolicy(allow_network=True, accept_terms=True,
                                 user_agent="Research contact@finpilot.invalid"), cik="123", opener=opener).fetch(
                                 "AAPL", "2024-01-01", "2024-12-31")
        def redirect(request, timeout):
            return FakeResponse(json.dumps(base).encode(), "https://unapproved.invalid/")
        with self.assertRaises(ProviderNetworkError):
            SecEdgarProvider(SourcePolicy(allow_network=True, accept_terms=True,
                             user_agent="Research contact@finpilot.invalid"), cik="123", opener=redirect).fetch(
                             "AAPL", "2024-01-01", "2024-12-31")

    def test_local_snapshot_missing_future_and_duplicate_input_use_old_rules(self):
        inputs = demo_inputs()
        with self.assertRaises(ProviderValidationError):
            UserSnapshotProvider().load("", "", inputs["as_of"])
        with self.assertRaisesRegex(ProviderValidationError, "重复"):
            UserSnapshotProvider().load(inputs["stocks_csv"], inputs["prices_csv"] + inputs["prices_csv"].splitlines()[1] + "\n", inputs["as_of"])
        result = UserSnapshotProvider().load(inputs["stocks_csv"], inputs["prices_csv"] + "2026-01-01,DEMO01,10\n", inputs["as_of"])
        self.assertEqual(result.provenance["future_price_rows_excluded"], 1)
        self.assertFalse(any(r.get("date") == "2026-01-01" for r in result.records))
        self.assertIn("DEMO08", [r["symbol"] for r in result.provenance["excluded_stocks"]])

    def test_doctor_checks_files_offline_with_existing_synthetic_labels(self):
        root = Path(__file__).resolve().parents[1]
        result = data_doctor(stocks_path=root / "examples/stocks_demo.csv", prices_path=root / "examples/prices_demo.csv", as_of="2025-12-31")
        self.assertFalse(result["network_called"])
        self.assertEqual(result["checks"][-1]["data_kind"], "synthetic")
        self.assertFalse(result["checks"][-1]["verified"])
        with self.assertRaises(ProviderValidationError):
            data_doctor(prices_path=root / "examples/prices_demo.csv")

    def test_cli_without_opt_in_is_actionable_and_creates_no_output(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "manifest.json"
            error = io.StringIO()
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as exit_code:
                main(["fetch", "--provider", "yfinance", "--ticker", "AAPL", "--start", "2024-01-01", "--end", "2024-01-03", "--output", str(path)])
            self.assertEqual(exit_code.exception.code, 2)
            self.assertIn("network disabled", error.getvalue())
            self.assertFalse(path.exists())

    def test_cli_fake_fetch_writes_manifest_and_compatible_prices_only_on_request(self):
        fake = FakeYFinance(price_frame())
        with tempfile.TemporaryDirectory() as folder:
            manifest = Path(folder) / "manifest.json"
            prices = Path(folder) / "prices.csv"
            with patch("finpilot.data_sources.importlib.import_module", return_value=fake), contextlib.redirect_stdout(io.StringIO()):
                main(["fetch", "--provider", "yfinance", "--ticker", "AAPL", "--start", "2024-01-01", "--end", "2024-01-03",
                      "--allow-network", "--accept-terms", "--output", str(manifest), "--prices-output", str(prices)])
            output = json.loads(manifest.read_text())
            self.assertFalse(output["verified"])
            self.assertEqual(output["data_kind"], "real_user_fetch")
            self.assertEqual(prices.read_text().splitlines()[0], "date,symbol,adj_close")

    def test_cli_local_csv_keeps_existing_hash_and_writes_separate_manifest(self):
        # Fake local numeric snapshot is a test input, not bundled real data.
        from finpilot.investment import STOCK_FIELDS, analyze_investment
        stocks = ",".join(STOCK_FIELDS) + "\n" + (
            "TEST,Fake Test Company,Test Sector,USD,2024-01-03,100,5,0.1,0.2,0.15,0.5,"
            "2023-09-30,2023-11-01,https://example.invalid/test-fixture\n"
        )
        prices = "date,symbol,adj_close\n2024-01-02,TEST,100\n2024-01-03,TEST,101\n"
        expected = analyze_investment(stocks, prices, "2024-01-03")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "stocks.csv").write_text(stocks, encoding="utf-8")
            (root / "prices.csv").write_text(prices, encoding="utf-8")
            stdout = io.StringIO()
            with patch("finpilot.data_sources.YFinanceProvider.fetch") as yf_fetch, \
                 patch("finpilot.data_sources.SecEdgarProvider.fetch") as sec_fetch, \
                 contextlib.redirect_stdout(stdout):
                main(["research", "--stocks", str(root / "stocks.csv"), "--prices", str(root / "prices.csv"),
                      "--as-of", "2024-01-03", "--output", str(root / "result")])
                yf_fetch.assert_not_called()
                sec_fetch.assert_not_called()
            output = json.loads(stdout.getvalue())
            research = json.loads((root / "result/research.json").read_text(encoding="utf-8"))
            manifest = json.loads((root / "result/input-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(research, expected)
            self.assertEqual(output["content_hash"], expected["content_hash"])
            self.assertEqual(output["data_kind"], "user_import")
            self.assertFalse(manifest["verified"])
            self.assertNotIn("records", manifest)
            self.assertEqual(manifest["provenance"]["input_hash"], research["input_hash"])

    def test_versioned_real_cases_are_templates_not_numeric_snapshots(self):
        root = Path(__file__).resolve().parents[1] / "examples/real_cases"
        cases = list(root.glob("case_*.json"))
        self.assertEqual(len(cases), 4)
        for path in cases:
            metadata = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["data_status"], "user_snapshot_required")
            self.assertEqual(metadata["case_type"], "实盘研究练习模板")
            self.assertEqual(metadata["schema_version"], "real-case-v1")
            self.assertTrue(metadata["questions"])
            self.assertTrue(all(url.startswith("https://") for url in metadata["source_urls"]))
            self.assertEqual(metadata["required_csv_fields"]["prices_csv"], ["date", "symbol", "adj_close"])
            self.assertNotIn("returns", metadata)
            self.assertNotIn("prices", metadata)


if __name__ == "__main__":
    unittest.main()

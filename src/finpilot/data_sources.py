"""Opt-in sources: local CSV, lazy yfinance, and bounded raw SEC companyfacts.

Importing this module or constructing an adapter performs no network/file I/O.
Fetches never fall back to fixtures and never imply independent verification.
The existing APIs in investment.py and data.py remain unchanged.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib
import importlib.util
import io
import json
import math
import re
import sys
from dataclasses import dataclass, field
from numbers import Integral, Real
from pathlib import Path
from typing import Any, Callable


class ProviderError(RuntimeError):
    """Actionable, fail-closed provider error."""


class ProviderPolicyError(ProviderError):
    pass


class ProviderDependencyError(ProviderError):
    pass


class ProviderNetworkError(ProviderError):
    pass


class ProviderValidationError(ProviderError, ValueError):
    pass


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")
_UNVERIFIED = "not_independently_verified"


def _date(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise ProviderValidationError(f"{label} must be YYYY-MM-DD")
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ProviderValidationError(f"{label} is not a valid calendar date") from exc


def _symbol(value: Any) -> str:
    if not isinstance(value, str) or not value.isascii() or not _SYMBOL_RE.fullmatch(value.upper()):
        raise ProviderValidationError("ticker must be 1-15 ASCII letters/digits/dots/hyphens, without whitespace")
    return value.upper()


def _hash_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _hash_json(value: Any) -> str:
    return _hash_bytes(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":")).encode("utf-8"))


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


@dataclass(frozen=True)
class SourcePolicy:
    """No network without both opt-ins. No keys, headers, or environment in manifests."""

    allow_network: bool = False
    accept_terms: bool = False
    user_agent: str | None = None
    timeout_seconds: float = 30.0
    max_response_bytes: int = 5_000_000
    max_records: int = 80_000
    max_days: int = 3660

    def __post_init__(self) -> None:
        if not isinstance(self.allow_network, bool) or not isinstance(self.accept_terms, bool):
            raise ProviderValidationError("allow_network and accept_terms must be booleans")
        if (isinstance(self.timeout_seconds, bool) or not isinstance(self.timeout_seconds, Real)
                or not math.isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 120):
            raise ProviderValidationError("timeout_seconds must be finite and in (0, 120]")
        for name, upper in (("max_response_bytes", 20_000_000), ("max_records", 80_000), ("max_days", 20_000)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or not 1 <= value <= upper:
                raise ProviderValidationError(f"{name} must be an integer in [1, {upper}]")
        if self.user_agent is not None and (
            not isinstance(self.user_agent, str) or not self.user_agent.strip()
            or len(self.user_agent) > 500 or "\r" in self.user_agent or "\n" in self.user_agent
        ):
            raise ProviderValidationError("user_agent must be a non-empty single line of at most 500 characters")

    def validate_bounds(self, start_date: str, end_date: str) -> tuple[str, str]:
        start, end = _date(start_date, "start_date"), _date(end_date, "end_date")
        first, last = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        if first > last:
            raise ProviderValidationError("start_date must not be after end_date")
        if last > dt.date.today():
            raise ProviderValidationError("end_date cannot be in the future")
        if (last - first).days > self.max_days:
            raise ProviderValidationError(f"date range exceeds max_days={self.max_days}")
        return start, end

    def require_network(self, provider: str) -> None:
        if not self.allow_network:
            raise ProviderPolicyError(f"{provider}: network disabled; use --allow-network explicitly. No request or synthetic fallback.")
        if not self.accept_terms:
            raise ProviderPolicyError(f"{provider}: review provider terms and pass --accept-terms. No request or synthetic fallback.")

    def metadata(self) -> dict[str, Any]:
        # Never serialize user_agent (contact PII), headers, or environment.
        return {"network_opt_in": self.allow_network, "terms_acknowledged": self.accept_terms,
                "timeout_seconds": self.timeout_seconds, "max_response_bytes": self.max_response_bytes,
                "max_records": self.max_records, "max_days": self.max_days,
                "adapter_cache": "none", "adapter_automatic_retries": 0}


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    data_kind: str
    requested_start: str | None
    requested_end: str | None
    records: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    verified: bool = False

    def __post_init__(self) -> None:
        if self.verified is not False:
            raise ProviderValidationError("fetch/import results cannot be marked verified")
        if self.data_kind not in {"user_import", "synthetic", "real_user_fetch"}:
            raise ProviderValidationError("unsupported provider data_kind")
        if not isinstance(self.records, list):
            raise ProviderValidationError("records must be a list")

    @property
    def record_count(self) -> int:
        return len(self.records)

    def to_dict(self) -> dict[str, Any]:
        label = {"user_import": "用户提供，未独立核验", "synthetic": "合成示例，非真实证券",
                 "real_user_fetch": "用户授权获取，未独立核验"}[self.data_kind]
        return {"schema_version": "provider-result-v1", "provider": self.provider,
                "data_kind": self.data_kind, "data_label": label, "verified": False,
                "verification_status": _UNVERIFIED, "requested_start": self.requested_start,
                "requested_end": self.requested_end, "record_count": len(self.records),
                "records": self.records, "provenance": self.provenance, "warnings": self.warnings}

    def prices_csv(self) -> str:
        """Return the legacy price header; retain the JSON manifest alongside it."""
        rows = [r for r in self.records if r.get("record_type") == "price"]
        if not rows:
            raise ProviderValidationError("result contains no price records; SEC facts are not prices")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["date", "symbol", "adj_close"], lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row[name] for name in writer.fieldnames})
        return output.getvalue()


class UserSnapshotProvider:
    """Reuse the existing CSV validation/point-in-time rules, without new semantics."""

    def load(self, stocks_csv: str, prices_csv: str = "", as_of: str = "2025-12-31") -> ProviderResult:
        # Lazy import keeps the external-source module independent of pandas/numpy.
        from .investment import PRICE_FIELDS, STOCK_FIELDS, _csv, analyze_investment
        try:
            research = analyze_investment(stocks_csv, prices_csv, as_of)
            stocks = [{"record_type": "stock_snapshot", **{k: row[k] for k in STOCK_FIELDS}}
                      for row in research["screen"]["rows"]]
            raw_prices = _csv(prices_csv, PRICE_FIELDS, "prices.csv", 80_000) if prices_csv.strip() else []
            prices = [{"record_type": "price", "date": r["date"], "symbol": r["symbol"],
                       "adj_close": float(r["adj_close"])} for r in raw_prices if r["date"] <= as_of]
        except ValueError as exc:
            raise ProviderValidationError(str(exc)) from exc
        return ProviderResult(
            "user_snapshot", research["data_kind"], None, as_of, stocks + prices,
            {"source": "caller-supplied local CSV", "verified": False,
             "verification_status": _UNVERIFIED, "input_hash": research["input_hash"],
             "stock_rows": len(stocks), "price_rows_visible": len(prices),
             "future_price_rows_excluded": len(raw_prices) - len(prices),
             "excluded_stocks": research["screen"]["excluded"],
             "authorization": "user responsibility; source strings are not proof of licensing"},
            research["warnings"],
        )


class YFinanceProvider:
    """Lazy yfinance download; adjusted close only, no implicit Close substitution."""

    def __init__(self, policy: SourcePolicy | None = None, *, yf_module: Any | None = None) -> None:
        self.policy = policy or SourcePolicy()
        self._yf = yf_module

    def _module(self) -> Any:
        if self._yf is None:
            try:
                self._yf = importlib.import_module("yfinance")
            except ImportError as exc:
                raise ProviderDependencyError(
                    "yfinance unavailable: optional dependency is not installed/usable. "
                    "Use authorized local CSV or prepare it separately; FinPilot will not install it or use synthetic fallback."
                ) from exc
        return self._yf

    def fetch(self, ticker: str, start_date: str, end_date: str) -> ProviderResult:
        symbol = _symbol(ticker)
        start, end = self.policy.validate_bounds(start_date, end_date)
        self.policy.require_network("yfinance")
        module = self._module()
        download = getattr(module, "download", None)
        if not callable(download):
            raise ProviderDependencyError("yfinance has no callable download; incompatible optional dependency")
        # Yahoo's end is exclusive; our public bounds are inclusive.
        request_end = (dt.date.fromisoformat(end) + dt.timedelta(days=1)).isoformat()
        request = {"ticker": symbol, "start": start, "end_inclusive": end,
                   "provider_end_exclusive": request_end, "interval": "1d", "auto_adjust": False,
                   "actions": False, "repair": False}
        try:
            frame = download(symbol, start=start, end=request_end, interval="1d", auto_adjust=False,
                             actions=False, repair=False, progress=False, threads=False,
                             group_by="column", timeout=self.policy.timeout_seconds)
        except Exception as exc:
            # Arbitrary provider exception text may contain credentials/headers.
            raise ProviderNetworkError(
                f"yfinance request failed ({type(exc).__name__}); check network/provider availability and terms locally. No synthetic fallback."
            ) from exc
        if frame is None or getattr(frame, "empty", True):
            raise ProviderValidationError("yfinance returned no data; check ticker, dates, network and terms. No synthetic fallback.")
        columns = getattr(frame, "columns", None)
        if columns is None or getattr(columns, "has_duplicates", True):
            raise ProviderValidationError("yfinance must return unique tabular columns")
        candidates = [c for c in columns if c == "Adj Close" or
                      (isinstance(c, tuple) and set(c) == {"Adj Close", symbol})]
        if len(candidates) != 1:
            raise ProviderValidationError("yfinance requires one Adj Close column for the requested ticker; Close is never substituted")
        series = frame[candidates[0]]
        if getattr(series, "ndim", None) != 1:
            raise ProviderValidationError("ambiguous yfinance adjusted-close shape")
        if len(series) > self.policy.max_records:
            raise ProviderValidationError("yfinance response exceeds max_records")
        records, seen = [], set()
        for raw_date, raw_value in series.items():
            # Preserve exchange calendar date, not a UTC date shifted from midnight.
            if not isinstance(raw_date, (dt.datetime, dt.date)):
                raise ProviderValidationError("yfinance date index must contain calendar timestamps")
            day = raw_date.date().isoformat() if isinstance(raw_date, dt.datetime) else raw_date.isoformat()
            day = _date(day, "yfinance date")
            if not start <= day <= end:
                raise ProviderValidationError("yfinance returned a date outside requested inclusive bounds")
            if day in seen:
                raise ProviderValidationError(f"yfinance duplicate calendar date: {day}")
            seen.add(day)
            if isinstance(raw_value, bool) or not isinstance(raw_value, Real) or not math.isfinite(raw_value) or raw_value <= 0:
                raise ProviderValidationError(f"yfinance Adj Close must be finite and positive on {day}; no filling")
            records.append({"record_type": "price", "date": day, "symbol": symbol,
                            "adj_close": float(raw_value)})
        if not records:
            raise ProviderValidationError("no adjusted-close records; no synthetic fallback")
        records.sort(key=lambda r: r["date"])
        provenance = {"source": "Yahoo Finance via unofficial yfinance library",
                      "source_locator": f"https://finance.yahoo.com/quote/{symbol}/history/",
                      "provider_version": str(getattr(module, "__version__", "unknown")),
                      "fetched_at": _utc_now(), "request": request, "policy": self.policy.metadata(),
                      "price_field": "Adj Close", "currency": "not supplied by this history adapter; user must check",
                      "verified": False, "verification_status": _UNVERIFIED,
                      "normalized_hash": _hash_json(records), "terms_url": "https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html"}
        return ProviderResult("yfinance", "real_user_fetch", start, end, records, provenance, [
            "User-authorized fetch is not independent verification, an official Yahoo API, or a data license.",
            "Adjusted history fetched today may include later corporate-action revisions; not a historical data vintage.",
            "FinPilot writes no adapter cache or secrets; yfinance may maintain its own internal cookie/timezone cache.",
            "Save the normalized manifest; check currency/adjustment conventions before combining with stocks.csv.",
        ])


class SecEdgarProvider:
    """Safe wrapper of the existing raw companyfacts capability, not a new financial mapper.

    The legacy data.SecEdgarProvider API is untouched. Its unbounded cached
    _get_json transport is deliberately NOT invoked. This wrapper uses the same
    public companyfacts endpoint, explicit CIK, bounded one-shot HTTP, no cache,
    no redirects, and an injected opener for offline tests. Raw facts are filtered
    by their *filed* date; no TTM/EPS/FCF or ticker-to-CIK guesses are made.
    """

    def __init__(self, policy: SourcePolicy | None = None, *, cik: str | None = None,
                 opener: Callable[..., Any] | None = None) -> None:
        self.policy = policy or SourcePolicy()
        self.cik = self._cik(cik) if cik is not None else None
        self._opener = opener

    @staticmethod
    def _cik(value: Any) -> str:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{1,10}", value) or int(value) == 0:
            raise ProviderValidationError("SEC requires an explicit nonzero 1-10 digit CIK; no ticker mapping guesses")
        return value.zfill(10)

    def _request_json(self, url: str) -> tuple[dict[str, Any], str]:
        # All SEC transport imports occur only on the explicit fetch path.
        from urllib.error import URLError
        from urllib.request import HTTPRedirectHandler, Request, build_opener
        agent = self.policy.user_agent
        if not agent or not re.search(r"[^\s@]+@[^\s@]+\.[^\s@]+", agent) or "example.com" in agent.lower():
            raise ProviderPolicyError("SEC requires a real contact user-agent, not the legacy example.com default; no request made")

        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ProviderNetworkError("SEC redirect rejected; only the fixed public endpoint is allowed")

        opener = self._opener or build_opener(NoRedirect()).open
        request = Request(url, headers={"User-Agent": agent, "Accept": "application/json",
                                       "Accept-Encoding": "identity"})
        try:
            with opener(request, timeout=self.policy.timeout_seconds) as response:
                response_url = response.geturl() if hasattr(response, "geturl") else url
                if response_url != url:
                    raise ProviderNetworkError("SEC response URL differs from the fixed endpoint")
                payload = response.read(self.policy.max_response_bytes + 1)
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderNetworkError(
                f"SEC request failed ({type(exc).__name__}); check network, rate limits and fair-access policy. No synthetic fallback."
            ) from exc
        if len(payload) > self.policy.max_response_bytes:
            raise ProviderNetworkError("SEC response exceeds max_response_bytes; no cache written")
        try:
            data = json.loads(payload.decode("utf-8"), parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ProviderValidationError("SEC response is not strict JSON") from exc
        if not isinstance(data, dict):
            raise ProviderValidationError("SEC response must be a JSON object")
        return data, _hash_bytes(payload)

    def fetch(self, ticker: str, start_date: str, end_date: str, *, cik: str | None = None) -> ProviderResult:
        symbol = _symbol(ticker)
        start, end = self.policy.validate_bounds(start_date, end_date)
        self.policy.require_network("sec_edgar")
        resolved = self._cik(cik) if cik is not None else self.cik
        if resolved is None:
            raise ProviderValidationError("SEC requires an explicit CIK via --cik; no ticker-to-CIK guess is performed")
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{resolved}.json"
        data, raw_hash = self._request_json(url)
        returned_cik = data.get("cik")
        if isinstance(returned_cik, bool) or not isinstance(returned_cik, (int, str)) or str(returned_cik).zfill(10) != resolved:
            raise ProviderValidationError("SEC response CIK does not match the requested company")
        facts = data.get("facts")
        if not isinstance(facts, dict) or not facts:
            raise ProviderValidationError("SEC companyfacts has no facts object; no synthetic fallback")
        records = []
        for taxonomy, tags in facts.items():
            if not isinstance(tags, dict):
                raise ProviderValidationError("SEC taxonomy must be an object")
            for tag, item in tags.items():
                if not isinstance(item, dict) or not isinstance(item.get("units"), dict):
                    raise ProviderValidationError("SEC fact requires explicit unit arrays")
                for unit, rows in item["units"].items():
                    if not isinstance(rows, list):
                        raise ProviderValidationError("SEC unit facts must be arrays")
                    for row in rows:
                        if not isinstance(row, dict):
                            raise ProviderValidationError("SEC fact row must be an object")
                        filed = _date(row.get("filed"), "SEC filed")
                        if not start <= filed <= end:
                            continue
                        period_end = _date(row.get("end"), "SEC fact end")
                        period_start = _date(row["start"], "SEC fact start") if "start" in row else None
                        if period_end > filed or (period_start and period_start > period_end):
                            raise ProviderValidationError("SEC fact period dates are inconsistent")
                        value = row.get("val")
                        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                            raise ProviderValidationError("SEC fact value must be finite numeric")
                        accession = row.get("accn")
                        if not isinstance(accession, str) or not re.fullmatch(r"[0-9]{10}-[0-9]{2}-[0-9]{6}", accession):
                            raise ProviderValidationError("SEC fact needs an accession number for provenance")
                        records.append({"record_type": "sec_raw_fact", "symbol": symbol, "cik": resolved,
                                        "taxonomy": taxonomy, "tag": tag, "unit": unit, "raw_fact": row,
                                        "source_locator": f"https://www.sec.gov/Archives/edgar/data/{int(resolved)}/{accession.replace('-', '')}/"})
                        if len(records) > self.policy.max_records:
                            raise ProviderValidationError("SEC normalized response exceeds max_records")
        if not records:
            raise ProviderValidationError("SEC returned no facts filed in requested bounds; no synthetic fallback")
        records.sort(key=lambda r: (r["raw_fact"]["filed"], r["taxonomy"], r["tag"], r["unit"], _hash_json(r)))
        return ProviderResult("sec_edgar", "real_user_fetch", start, end, records, {
            "source": "SEC EDGAR raw companyfacts", "source_locator": url, "cik": resolved,
            "requested_ticker": symbol, "ticker_cik_mapping": "caller supplied; not independently verified",
            "fetched_at": _utc_now(), "request": {"filed_start_inclusive": start, "filed_end_inclusive": end},
            "date_bounds_semantics": "filter raw facts by filed date, NOT a historical response vintage",
            "raw_response_hash": raw_hash, "normalized_hash": _hash_json(records),
            "policy": self.policy.metadata(), "verified": False, "verification_status": _UNVERIFIED,
            "terms_url": "https://www.sec.gov/os/accessing-edgar-data",
        }, ["Raw companyfacts only: no accounting mapping, fact deduplication, TTM/EPS/FCF derivation or stock CSV generation.",
            "Current companyfacts can contain amendments/restatements; filed-date filtering does not restore historical vintages.",
            "Ticker/CIK, taxonomy, units, fiscal periods and the original filing need human review; an official endpoint is not verification."])


def dependency_status() -> dict[str, Any]:
    """Inspect package availability without importing yfinance or contacting sources."""
    try:
        installed = importlib.util.find_spec("yfinance") is not None
    except (ImportError, ValueError):
        installed = False
    return {"python_version": sys.version.split()[0], "optional": {
        "yfinance": {"installed": installed, "imported": "yfinance" in sys.modules}},
        "network_called": False, "adapter_cache_written": False}


def _read_local_csv(path: str | Path) -> str:
    with Path(path).open("rb") as handle:
        raw = handle.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ProviderValidationError("local CSV exceeds 2MB")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ProviderValidationError("local CSV must be UTF-8") from exc


def data_doctor(*, provider: str | None = None, stocks_path: str | Path | None = None,
                prices_path: str | Path | None = None, as_of: str | None = None) -> dict[str, Any]:
    """Offline diagnostic, never a download or source-authenticity assertion."""
    if provider not in {None, "yfinance", "sec_edgar", "user_snapshot"}:
        raise ProviderValidationError(f"unknown provider: {provider}")
    if prices_path and not stocks_path:
        raise ProviderValidationError("--prices requires --stocks to validate identifiers/currency")
    if as_of:
        _date(as_of, "as_of")
    runtime = dependency_status()
    checks = [{"name": "runtime", "status": "ok", **runtime}]
    if provider == "yfinance":
        installed = runtime["optional"]["yfinance"]["installed"]
        checks.append({"name": "yfinance_dependency", "status": "ok" if installed else "review",
                       "message": "optional package available; no fetch attempted" if installed else "optional package absent; nothing was installed"})
    if provider == "sec_edgar":
        checks.append({"name": "sec_transport", "status": "review",
                       "message": "stdlib raw companyfacts adapter; fetch still requires opt-ins, explicit CIK and real contact user-agent"})
    if stocks_path:
        snapshot = UserSnapshotProvider().load(_read_local_csv(stocks_path),
                                               _read_local_csv(prices_path) if prices_path else "",
                                               as_of or dt.date.today().isoformat())
        needs_review = bool(snapshot.provenance["excluded_stocks"] or snapshot.provenance["future_price_rows_excluded"])
        checks.append({"name": "local_snapshot", "status": "review" if needs_review else "ok",
                       "data_kind": snapshot.data_kind, "verified": False,
                       "record_count": len(snapshot.records), "provenance": snapshot.provenance,
                       "warnings": snapshot.warnings})
    return {"schema_version": "data-doctor-v1", "status": "review" if any(c["status"] == "review" for c in checks) else "ok",
            "checks": checks, "network_called": False, "cache_written": False,
            "synthetic_fallback": False, "scope": "offline engineering checks, not a source verification or license review"}

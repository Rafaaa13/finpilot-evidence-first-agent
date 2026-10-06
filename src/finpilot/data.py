from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .domain import Evidence, Observation


# The fixture is deliberately a corpus, rather than a function of the requested
# cutoff.  A caller can therefore compare two as-of dates without the old rows
# changing underneath it.
FIXTURE_SEED = 20241003
INTERNAL_FIXTURE_TICKER = "DEMO"
DEFAULT_AS_OF = "2025-12-31"
MIN_FIXTURE_DATE = "2021-01-01"
MAX_FIXTURE_DATE = "2026-12-31"
_TICKER_RE = re.compile(r"^[A-Za-z]{1,5}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class DataValidationError(ValueError):
    """Raised when a provider input or normalized observation is unsafe."""


def validate_ticker(ticker: str) -> str:
    """Validate and normalize a plain US-style ticker used by the providers.

    Fixture data never uses this value as the identity of a real security; the
    fixture's observations are always labelled ``DEMO``.  Lowercase input is
    accepted for compatibility with the existing CLI, while whitespace,
    punctuation, and empty strings are rejected.
    """

    if not isinstance(ticker, str) or not _TICKER_RE.fullmatch(ticker):
        raise DataValidationError("ticker must contain 1-5 ASCII letters and no whitespace")
    return ticker.upper()


def validate_as_of(as_of: str) -> str:
    """Validate an ISO calendar date within the fixture's bounded corpus."""

    if not isinstance(as_of, str) or not _DATE_RE.fullmatch(as_of):
        raise DataValidationError("as_of must be an ISO date in YYYY-MM-DD form")
    try:
        parsed = dt.date.fromisoformat(as_of)
    except ValueError as exc:
        raise DataValidationError(f"invalid as_of date: {as_of!r}") from exc
    lower = dt.date.fromisoformat(MIN_FIXTURE_DATE)
    upper = dt.date.fromisoformat(MAX_FIXTURE_DATE)
    if parsed < lower or parsed > upper:
        raise DataValidationError(
            f"as_of must be between {MIN_FIXTURE_DATE} and {MAX_FIXTURE_DATE}"
        )
    return parsed.isoformat()


def _parse_optional_date(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _DATE_RE.fullmatch(value):
        raise DataValidationError(f"{field_name} must be null or an ISO date")
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise DataValidationError(f"invalid {field_name}: {value!r}") from exc


def _canonical_hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise DataValidationError("hash input must be finite JSON data") from exc
    return hashlib.sha256(encoded).hexdigest()


def _sha256_ref(value: Any) -> str:
    return f"sha256:{_canonical_hash(value)}"


def _observation(
    *,
    entity_id: str,
    metric: str,
    value: float | int | str | None,
    unit: str,
    period_start: str | None,
    period_end: str | None,
    filed_at: str | None,
    effective_at: str,
    source: str,
    source_locator: str,
    quality_status: str = "valid",
    formula: str | None = None,
) -> Observation:
    raw_record = {
        "entity_id": entity_id,
        "metric": metric,
        "value": value,
        "unit": unit,
        "period_start": period_start,
        "period_end": period_end,
        "filed_at": filed_at,
        "effective_at": effective_at,
        "source": source,
        "source_locator": source_locator,
        "quality_status": quality_status,
        "formula": formula,
    }
    return Observation(raw_ref=_sha256_ref(raw_record), **raw_record)


class DataProvider(Protocol):
    def load(self, ticker: str, as_of: str) -> "Dataset": ...

    def observations(self, ticker: str, as_of: str) -> list[Observation]: ...

    def evidence(self, ticker: str, as_of: str) -> list[Evidence]: ...


@dataclass
class Dataset:
    observations: list[Observation]
    evidence: list[Evidence]
    source_name: str
    metadata: dict[str, Any]


class FixtureProvider:
    """Deterministic synthetic data for offline demos and regression tests.

    The full corpus is generated with one fixed seed and then point-in-time
    filtered.  ``AAPL`` and ``MSFT`` are accepted as convenient demo inputs,
    but neither is used as an identity in the returned observations: every row
    is explicitly labelled ``DEMO`` and every source is marked synthetic.
    """

    seed = FIXTURE_SEED
    internal_ticker = INTERNAL_FIXTURE_TICKER
    default_as_of = DEFAULT_AS_OF

    def load(self, ticker: str, as_of: str = DEFAULT_AS_OF) -> Dataset:
        requested_ticker = validate_ticker(ticker)
        cutoff = dt.date.fromisoformat(validate_as_of(as_of))
        all_rows, all_evidence = self._build_corpus()

        visible_rows = [row for row in all_rows if self._visible(row, cutoff)]
        visible_evidence = [
            evidence
            for evidence in all_evidence
            if self._evidence_visible(evidence, cutoff)
        ]
        source_hashes = self._source_hashes(all_rows)
        evidence_hashes = {
            evidence.evidence_id: _sha256_ref(evidence.to_dict())
            for evidence in all_evidence
        }
        missing: list[str] = []
        if not any(row.metric == "close" for row in visible_rows):
            missing.append("market")
        if not any(row.metric != "close" for row in visible_rows):
            missing.append("fundamentals")

        metadata: dict[str, Any] = {
            "seed": self.seed,
            "synthetic": True,
            "synthetic_label": (
                "SYNTHETIC FIXTURE / DEMO ticker — educational data, not a real security"
            ),
            "internal_ticker": self.internal_ticker,
            "requested_ticker": requested_ticker,
            "as_of": cutoff.isoformat(),
            "generated_date_range": {
                "start": "2021-01-01",
                "end": MAX_FIXTURE_DATE,
            },
            "visibility": {
                "market": "effective_at <= as_of",
                "fundamentals": "filed_at <= as_of",
            },
            "price_model": (
                "fixed-seed zero-drift stochastic walk with positive and negative shocks; "
                "not tuned for performance"
            ),
            "source_hashes": source_hashes,
            "evidence_hashes": evidence_hashes,
            "observation_count_full_corpus": len(all_rows),
            "evidence_count_full_corpus": len(all_evidence),
        }
        if missing:
            metadata["missing"] = missing
        return Dataset(
            observations=visible_rows,
            evidence=visible_evidence,
            source_name="fixture-synthetic",
            metadata=metadata,
        )

    def observations(self, ticker: str, as_of: str = DEFAULT_AS_OF) -> list[Observation]:
        return self.load(ticker, as_of).observations

    def evidence(self, ticker: str, as_of: str = DEFAULT_AS_OF) -> list[Evidence]:
        return self.load(ticker, as_of).evidence

    @classmethod
    def _build_corpus(cls) -> tuple[list[Observation], list[Evidence]]:
        rows: list[Observation] = []
        evidence: list[Evidence] = []

        # Annual fundamentals are generated independently from the market RNG,
        # but remain fixed for all requested tickers and cutoffs.
        fundamentals_rng = random.Random(cls.seed ^ 0x51EC0DE)
        base_revenue = 420_000.0
        growth = 0.075
        annual_values: dict[int, dict[str, float]] = {}
        for index, year in enumerate(range(2021, 2026)):
            # Small, deterministic variation avoids perfectly smooth textbook
            # values without changing the point-in-time behavior.
            noise = fundamentals_rng.uniform(-0.012, 0.012)
            revenue = base_revenue * ((1 + growth) ** index) * (1 + noise)
            op_margin = 0.17 + fundamentals_rng.uniform(-0.018, 0.018)
            fcf_margin = 0.105 + fundamentals_rng.uniform(-0.016, 0.016)
            annual_values[year] = {
                "revenue": revenue,
                "operating_income": revenue * op_margin,
                "free_cash_flow": revenue * fcf_margin,
            }
            filed_at = f"{year + 1:04d}-02-15"
            for metric, value in annual_values[year].items():
                rows.append(
                    _observation(
                        entity_id=cls.internal_ticker,
                        metric=metric,
                        value=round(value, 4),
                        unit="USD_mm",
                        period_start=f"{year:04d}-01-01",
                        period_end=f"{year:04d}-12-31",
                        filed_at=filed_at,
                        effective_at=filed_at,
                        source="fixture-sec",
                        source_locator=f"fixture://synthetic/sec/{cls.internal_ticker}/{year}",
                        formula="fixed-seed synthetic annual fixture; not a filed value",
                    )
                )
            evidence.append(
                Evidence(
                    evidence_id=f"ev-sec-{cls.internal_ticker}-{year}",
                    title=f"[SYNTHETIC FIXTURE] Annual filing-shaped data {year}",
                    source="fixture-sec",
                    locator=f"fixture://synthetic/sec/{cls.internal_ticker}/{year}",
                    as_of=filed_at,
                    excerpt=(
                        "Synthetic educational filing-shaped record; not SEC data and not "
                        f"a real security filing for FY{year}."
                    ),
                    supports=tuple(
                        f"{metric}-{year}" for metric in annual_values[year]
                    ),
                )
            )

        # Daily prices use a fixed random walk with near-zero drift and a
        # meaningful shock size.  This intentionally produces both up and down
        # days rather than a monotonic series that flatters momentum metrics.
        market_rng = random.Random(cls.seed ^ 0x4D41524B)
        price = 120.0
        market_dates = _business_days("2022-01-03", MAX_FIXTURE_DATE)
        for index, date in enumerate(market_dates):
            cyclical = 0.00035 * math.sin(index / 13.0)
            shock = market_rng.gauss(0.0, 0.014)
            # A tiny negative drift prevents the educational series from being
            # an implicitly optimized long-only success story.
            daily_return = max(-0.08, min(0.08, shock + cyclical - 0.00003))
            price *= 1.0 + daily_return
            rows.append(
                _observation(
                    entity_id=cls.internal_ticker,
                    metric="close",
                    value=round(price, 6),
                    unit="USD",
                    period_start=date,
                    period_end=date,
                    filed_at=None,
                    effective_at=date,
                    source="fixture-market",
                    source_locator=f"fixture://synthetic/market/{cls.internal_ticker}/{date}",
                )
            )
        evidence.append(
            Evidence(
                evidence_id=f"ev-market-{cls.internal_ticker}",
                title="[SYNTHETIC FIXTURE] Daily market-shaped series",
                source="fixture-market",
                locator=f"fixture://synthetic/market/{cls.internal_ticker}",
                as_of="2022-01-03",
                excerpt=(
                    "Fixed-seed synthetic close prices with positive and negative daily "
                    "shocks; not Yahoo Finance data and not a real security."
                ),
                supports=("close",),
            )
        )
        return rows, evidence

    @staticmethod
    def _visible(row: Observation, cutoff: dt.date) -> bool:
        effective = dt.date.fromisoformat(row.effective_at)
        if row.metric == "close":
            return effective <= cutoff
        if row.filed_at is None:
            return False
        return dt.date.fromisoformat(row.filed_at) <= cutoff

    @staticmethod
    def _evidence_visible(evidence: Evidence, cutoff: dt.date) -> bool:
        # The market evidence is available as soon as the first market row is
        # available; annual evidence follows its explicit filing date.
        evidence_date = dt.date.fromisoformat(evidence.as_of)
        if evidence.source == "fixture-market":
            return cutoff >= dt.date(2022, 1, 3)
        return evidence_date <= cutoff

    @staticmethod
    def _source_hashes(rows: list[Observation]) -> dict[str, str]:
        by_source: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            by_source.setdefault(row.source, []).append(row.to_dict())
        return {
            source: _sha256_ref(sorted(values, key=lambda value: (value["metric"], value["effective_at"])))
            for source, values in sorted(by_source.items())
        }



def _business_days(start: str, end: str) -> list[str]:
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    if s > e:
        return []
    out: list[str] = []
    while s <= e:
        if s.weekday() < 5:
            out.append(s.isoformat())
        s += dt.timedelta(days=1)
    return out


class SecEdgarProvider:
    """Small, cached SEC companyfacts adapter; live mode is opt-in.

    The direct adapter remains intentionally incomplete.  Production SEC access
    should be wired through the configured read-only MCP server in
    :mod:`finpilot.integrations`; this class never makes a request merely by
    being imported or instantiated.
    """

    def __init__(self, cache_dir: str | Path = "data/raw/sec", user_agent: str | None = None):
        self.cache_dir = Path(cache_dir)
        self.user_agent = user_agent or os.getenv(
            "EDGAR_USER_AGENT", "FinPilot research demo research@example.com"
        )

    def _get_json(self, url: str, filename: str) -> dict[str, Any]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / filename
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        req = Request(url, headers={"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"})
        try:
            with urlopen(req, timeout=30) as response:
                payload = response.read()
        except (HTTPError, URLError) as exc:
            raise RuntimeError(f"SEC request failed: {exc}") from exc
        path.write_bytes(payload)
        time.sleep(0.2)
        return json.loads(payload.decode("utf-8"))

    def observations(self, ticker: str, as_of: str) -> list[Observation]:
        validate_ticker(ticker)
        validate_as_of(as_of)
        raise RuntimeError(
            "Live SEC adapter needs a ticker-to-CIK mapping; use the configured MCP "
            "server or fixture mode."
        )

    def evidence(self, ticker: str, as_of: str) -> list[Evidence]:
        validate_ticker(ticker)
        validate_as_of(as_of)
        return []

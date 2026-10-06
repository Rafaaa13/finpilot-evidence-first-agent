from __future__ import annotations

"""Point-in-time analytics used by the deterministic FinPilot fixture.

The functions in this module are deliberately small and auditable.  They are
not investment or regulatory models: all annualisation constants and scoring
weights are educational assumptions, and callers should retain the
``formula_refs`` returned with each result.
"""

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd

from .domain import Observation


_MARKET_METRICS = {"close", "adj_close", "open", "high", "low", "volume"}


def _as_dict(observation: Observation | dict[str, Any]) -> dict[str, Any]:
    if hasattr(observation, "to_dict"):
        return observation.to_dict()  # type: ignore[no-any-return]
    return dict(observation)


def _finite(value: Any) -> float | None:
    """Return a finite Python float, or ``None`` for missing/non-finite data."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _date_iso(value: Any) -> str | None:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(timestamp):
        return None
    return timestamp.date().isoformat()


def _empty_market(status: str, as_of: str, warning: str) -> dict[str, Any]:
    return {
        "status": status,
        "as_of": as_of,
        "last_close": None,
        "return_20d": None,
        "return_60d": None,
        "volatility_20d": None,
        "max_drawdown": None,
        "observations": 0,
        "warnings": [warning],
        "formula_refs": [
            "return_n = close_t / close_(t-n) - 1",
            "volatility = sample_std(daily_return, ddof=1) * sqrt(252)",
            "drawdown = close / running_peak - 1; max_drawdown = min(drawdown)",
        ],
    }


def frames(observations: Iterable[Observation | dict[str, Any]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split observations into tidy market and fundamental frames.

    Market observations are point-in-time values keyed by ``effective_at``.
    Fundamental observations remain filing-aware and expose both the filing
    date and period end so downstream calculations can enforce an as-of cut.
    Invalid dates or numeric values are discarded rather than guessed.
    """
    rows = [_as_dict(o) for o in observations]
    market_rows = [row for row in rows if str(row.get("metric", "")).lower() in _MARKET_METRICS]
    fundamental_rows = [row for row in rows if str(row.get("metric", "")).lower() not in _MARKET_METRICS]

    if market_rows:
        raw_market = pd.DataFrame(market_rows)
        raw_market["date"] = pd.to_datetime(raw_market.get("effective_at"), errors="coerce")
        raw_market["numeric_value"] = pd.to_numeric(raw_market.get("value"), errors="coerce")
        raw_market = raw_market.dropna(subset=["date", "numeric_value"])
        if not raw_market.empty:
            # A wide frame keeps optional OHLC data available to a caller while
            # retaining the contract's canonical ``close`` column.
            market = (
                raw_market.assign(metric=raw_market["metric"].astype(str).str.lower())
                .pivot_table(index="date", columns="metric", values="numeric_value", aggfunc="last")
                .reset_index()
                .sort_values("date")
            )
            market.columns.name = None
            if "close" not in market.columns and "adj_close" in market.columns:
                market["close"] = market["adj_close"]
            if "close" in market.columns:
                market["close"] = pd.to_numeric(market["close"], errors="coerce")
                market = market.dropna(subset=["close"])
                market["return_1d"] = market["close"].pct_change()
        else:
            market = pd.DataFrame(columns=["date", "close", "return_1d"])
    else:
        market = pd.DataFrame(columns=["date", "close", "return_1d"])

    if fundamental_rows:
        fundamentals = pd.DataFrame(fundamental_rows)
        fundamentals["filed_date"] = pd.to_datetime(fundamentals.get("filed_at"), errors="coerce")
        fundamentals["period_date"] = pd.to_datetime(fundamentals.get("period_end"), errors="coerce")
        fundamentals["value"] = pd.to_numeric(fundamentals.get("value"), errors="coerce")
        fundamentals = fundamentals.dropna(subset=["filed_date", "value"])
        fundamentals = fundamentals.sort_values(["filed_date", "period_date", "metric"])
    else:
        fundamentals = pd.DataFrame(columns=["metric", "value", "filed_date", "period_date"])

    return market.reset_index(drop=True), fundamentals.reset_index(drop=True)


def market_features(market: pd.DataFrame, as_of: str) -> dict[str, Any]:
    """Compute point-in-time market features through ``as_of`` only."""
    try:
        cutoff = pd.Timestamp(as_of)
    except (TypeError, ValueError):
        return _empty_market("invalid", str(as_of), "as_of is not a valid date")
    if pd.isna(cutoff):
        return _empty_market("invalid", str(as_of), "as_of is not a valid date")

    if market is None or market.empty:
        return _empty_market("missing", _date_iso(cutoff) or str(as_of), "No market observations")

    m = market.copy()
    if "date" not in m.columns:
        if "effective_at" in m.columns:
            m["date"] = pd.to_datetime(m["effective_at"], errors="coerce")
        else:
            return _empty_market("invalid", _date_iso(cutoff) or str(as_of), "Market frame has no date column")
    else:
        m["date"] = pd.to_datetime(m["date"], errors="coerce")
    if "close" not in m.columns:
        if "adj_close" in m.columns:
            m["close"] = m["adj_close"]
        elif "value" in m.columns:
            m["close"] = m["value"]
        else:
            return _empty_market("invalid", _date_iso(cutoff) or str(as_of), "Market frame has no close column")
    m["close"] = pd.to_numeric(m["close"], errors="coerce")
    m = m.dropna(subset=["date", "close"])
    m = m[m["date"] <= cutoff].sort_values("date").drop_duplicates("date", keep="last")
    m = m[m["close"] > 0]
    if m.empty:
        return _empty_market("missing", _date_iso(cutoff) or str(as_of), "No valid market observations as of requested date")

    close = m["close"].astype(float).reset_index(drop=True)
    daily_returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()

    def trailing_return(window: int) -> float | None:
        if len(close) <= window:
            return None
        return _finite(close.iloc[-1] / close.iloc[-window - 1] - 1.0)

    recent_returns = daily_returns.tail(20)
    volatility = _finite(recent_returns.std(ddof=1) * math.sqrt(252)) if len(recent_returns) >= 2 else None
    drawdown = close / close.cummax() - 1.0
    max_drawdown = _finite(drawdown.min())
    warnings: list[str] = []
    if len(close) <= 20:
        warnings.append("insufficient_history_for_20d_return")
    if len(close) <= 60:
        warnings.append("insufficient_history_for_60d_return")
    if len(recent_returns) < 2:
        warnings.append("insufficient_history_for_volatility")

    return {
        "status": "valid",
        "as_of": _date_iso(cutoff) or str(as_of),
        "last_close": _finite(close.iloc[-1]),
        "return_20d": trailing_return(20),
        "return_60d": trailing_return(60),
        "volatility_20d": volatility,
        "max_drawdown": max_drawdown,
        "observations": int(len(close)),
        "warnings": warnings,
        "formula_refs": [
            "return_n = close_t / close_(t-n) - 1",
            "volatility = sample_std(daily_return, ddof=1) * sqrt(252)",
            "drawdown = close / running_peak - 1; max_drawdown = min(drawdown)",
        ],
    }


def fundamental_features(fundamentals: pd.DataFrame, as_of: str) -> dict[str, Any]:
    """Compute filing-aware fundamentals without using filings after ``as_of``."""
    formula_refs = [
        "revenue_growth_yoy = revenue_t / revenue_(t-1) - 1",
        "operating_margin = operating_income / revenue",
        "fcf_margin = free_cash_flow / revenue",
        "latest filing is selected only from filed_at <= as_of",
    ]
    try:
        cutoff = pd.Timestamp(as_of)
    except (TypeError, ValueError):
        return {"status": "invalid", "as_of": str(as_of), "latest": {}, "warnings": ["as_of is not a valid date"], "formula_refs": formula_refs}
    if pd.isna(cutoff):
        return {"status": "invalid", "as_of": str(as_of), "latest": {}, "warnings": ["as_of is not a valid date"], "formula_refs": formula_refs}
    if fundamentals is None or fundamentals.empty:
        return {"status": "missing", "as_of": _date_iso(cutoff), "latest": {}, "warnings": ["No fundamentals available"], "formula_refs": formula_refs}

    f = fundamentals.copy()
    if "filed_date" not in f.columns:
        if "filed_at" in f.columns:
            f["filed_date"] = pd.to_datetime(f["filed_at"], errors="coerce")
        else:
            return {"status": "invalid", "as_of": _date_iso(cutoff), "latest": {}, "warnings": ["Fundamental frame has no filing date"], "formula_refs": formula_refs}
    else:
        f["filed_date"] = pd.to_datetime(f["filed_date"], errors="coerce")
    if "period_date" not in f.columns:
        f["period_date"] = pd.to_datetime(f.get("period_end"), errors="coerce")
    else:
        f["period_date"] = pd.to_datetime(f["period_date"], errors="coerce")
    f["value"] = pd.to_numeric(f.get("value"), errors="coerce")
    f = f.dropna(subset=["filed_date", "value"])
    f = f[f["filed_date"] <= cutoff].copy()
    if f.empty:
        return {"status": "missing", "as_of": _date_iso(cutoff), "latest": {}, "warnings": ["No filings available as of requested date"], "formula_refs": formula_refs}

    # For each metric and reporting period retain the latest visible filing;
    # this prevents a restatement from being silently mixed with an older fact.
    f["metric"] = f.get("metric", "unknown").astype(str)
    f = f.sort_values(["metric", "period_date", "filed_date"])
    f = f.drop_duplicates(["metric", "period_date"], keep="last")
    series: dict[str, list[float]] = {}
    latest: dict[str, float] = {}
    for metric, group in f.groupby("metric", sort=True):
        group = group.sort_values(["period_date", "filed_date"], na_position="first")
        values = [_finite(v) for v in group["value"]]
        values = [v for v in values if v is not None]
        if values:
            series[metric] = values
            latest[metric] = values[-1]

    warnings = []
    rev_rows = f[f['metric'] == 'revenue'].sort_values('period_date')
    revenue_growth = operating_margin = fcf_margin = None
    if not rev_rows.empty:
        latest_row = rev_rows.iloc[-1]
        rv = float(latest_row['value'])
        start, end = latest_row.get('period_start'), latest_row.get('period_end')
        unit = latest_row.get('unit')
        for metric in ('operating_income', 'free_cash_flow'):
            candidates = f[(f['metric'] == metric) & (f['period_end'] == end) & (f['period_start'] == start) & (f['unit'] == unit)]
            margin = _finite(candidates.iloc[-1]['value'] / rv) if len(candidates) and rv != 0 else None
            if metric == 'operating_income': operating_margin = margin
            else: fcf_margin = margin
        if len(rev_rows) >= 2:
            prior = rev_rows.iloc[-2]
            span = (pd.Timestamp(end) - pd.Timestamp(start)).days if start and end else 0
            prev_span = (pd.Timestamp(prior.get('period_end')) - pd.Timestamp(prior.get('period_start'))).days if prior.get('period_start') else 0
            gap = (latest_row['period_date'] - prior['period_date']).days
            if 330 <= span <= 380 and 330 <= prev_span <= 380 and 330 <= gap <= 400 and prior.get('unit') == unit and prior['value'] != 0:
                revenue_growth = _finite(rv / prior['value'] - 1)
    if revenue_growth is None: warnings.append('insufficient_comparable_annual_revenue')
    if operating_margin is None or fcf_margin is None: warnings.append('missing_matching_period_or_unit_for_margin')
    latest_filed = f["filed_date"].max()

    return {
        "status": "valid",
        "as_of": _date_iso(cutoff),
        "latest": latest,
        "revenue_growth_yoy": revenue_growth,
        "operating_margin": operating_margin,
        "fcf_margin": fcf_margin,
        "latest_filed_at": _date_iso(latest_filed),
        "warnings": warnings,
        "formula_refs": formula_refs,
    }


def risk_snapshot(market: dict[str, Any], fundamentals: dict[str, Any]) -> dict[str, Any]:
    """Apply transparent review flags; this is a gate, not a probability model."""
    market = market or {}
    fundamentals = fundamentals or {}
    flags: list[str] = []
    volatility = _finite(market.get("volatility_20d"))
    drawdown = _finite(market.get("max_drawdown"))
    if volatility is not None and volatility > 0.45:
        flags.append("volatility_above_45%")
    if drawdown is not None and drawdown < -0.25:
        flags.append("drawdown_below_-25%")
    if _finite(fundamentals.get("operating_margin")) is not None and float(fundamentals["operating_margin"]) < 0:
        flags.append("negative_operating_margin")
    if _finite(fundamentals.get("fcf_margin")) is not None and float(fundamentals["fcf_margin"]) < 0:
        flags.append("negative_fcf_margin")
    data_quality = [market.get("status", "missing"), fundamentals.get("status", "missing")]
    if "missing" in data_quality or "invalid" in data_quality:
        flags.append("incomplete_data")
    return {
        "status": "review" if flags else "pass",
        "flags": flags,
        "data_quality": data_quality,
        "formula_refs": [
            "review if annualized 20d volatility > 45%",
            "review if maximum drawdown < -25%",
            "review if operating or FCF margin is negative",
        ],
    }


def composite_score(market: dict[str, Any], fundamentals: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    """Return a descriptive heuristic score with a correctly signed risk penalty.

    In particular, drawdown is converted to *drawdown depth* before scoring:
    a more negative drawdown increases the penalty and therefore cannot improve
    the score by accident.
    """
    market = market or {}
    fundamentals = fundamentals or {}
    risk = risk or {}

    def zish(value: Any, center: float = 0.0, scale: float = 0.1) -> float:
        number = _finite(value)
        if number is None or scale <= 0:
            return 0.0
        return max(-2.0, min(2.0, (number - center) / scale))

    momentum = 0.6 * zish(market.get("return_20d")) + 0.4 * zish(market.get("return_60d"), scale=0.2)
    quality = 0.45 * zish(fundamentals.get("revenue_growth_yoy"), scale=0.1) + 0.55 * zish(fundamentals.get("fcf_margin"), center=0.1, scale=0.1)

    volatility = _finite(market.get("volatility_20d"))
    drawdown = _finite(market.get("max_drawdown"))
    volatility_excess = max(0.0, zish(volatility, center=0.25, scale=0.15)) if volatility is not None else 0.0
    # Convert a negative drawdown into a positive depth.  This fixes the
    # common sign error where a larger loss reduced a nominal "penalty".
    drawdown_depth = max(0.0, ((-drawdown) - 0.10) / 0.20) if drawdown is not None else 0.0
    drawdown_excess = max(0.0, min(2.0, drawdown_depth))
    risk_penalty = 0.6 * volatility_excess + 0.4 * drawdown_excess
    score = 0.5 * momentum + 0.3 * quality - 0.2 * risk_penalty

    has_signal = any(
        _finite(market.get(key)) is not None for key in ("return_20d", "return_60d", "volatility_20d", "max_drawdown")
    ) or any(_finite(fundamentals.get(key)) is not None for key in ("revenue_growth_yoy", "operating_margin", "fcf_margin"))
    return {
        "score": _finite(score) if has_signal else None,
        "components": {
            "momentum": _finite(momentum),
            "quality": _finite(quality),
            "risk_penalty": _finite(risk_penalty),
            "volatility_excess": _finite(volatility_excess),
            "drawdown_excess": _finite(drawdown_excess),
        },
        "formula": "0.50*momentum + 0.30*quality - 0.20*risk_penalty",
        "risk_flags": list(risk.get("flags", [])),
        "caveat": "Descriptive nonvalidated heuristic; not investment advice or a calibrated forecast.",
    }

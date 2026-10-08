"""Deterministic, long-only allocations and current-weight risk diagnostics.

No optimisation or investment-performance claim is made. Cash earns zero in
stress scenarios; historical replays are not executable trading backtests.
"""
from __future__ import annotations

import math
from numbers import Integral, Real
from typing import Any

import numpy as np
import pandas as pd


_DEFAULT_Z = 1.645  # Conventional rounded one-sided 95% normal quantile.
_DEFAULT_SCENARIOS = (
    {"name": "parametric_95", "type": "parametric"},
    {"name": "worst_20d_replay", "type": "historical", "window": 20},
    {"name": "correlation_95", "type": "correlation", "rho": 0.95},
)
_HISTORICAL_TYPES = {"historical", "historical_replay", "historical_fixed_weight"}


def _number(value: Any, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise ValueError(f"{name} must be a finite real number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite real number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be a finite real number")
    return result


def _positive_integer(value: Any, name: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return int(value)


def _entity_id(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("entity_id must be a non-empty string")
    return value


def _screen_rows(screen_result: Any) -> tuple[list[str], dict[str, dict[str, Any]]]:
    if not isinstance(screen_result, dict):
        raise ValueError("screen_result must be a mapping")
    selected, rows = screen_result.get("selected"), screen_result.get("rows")
    if not isinstance(selected, (list, tuple)) or not isinstance(rows, (list, tuple)):
        raise ValueError("screen_result must contain selected IDs and rows lists")
    row_map: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not {"entity_id", "sector", "score", "market", "evidence_ids"} <= row.keys():
            raise ValueError("each screen row must contain entity_id, sector, score, market, evidence_ids")
        entity = _entity_id(row["entity_id"])
        if entity in row_map:
            raise ValueError(f"duplicate row entity_id: {entity}")
        if not isinstance(row["sector"], str):
            raise ValueError(f"{entity}.sector must be a string")
        if not isinstance(row["score"], dict) or "score" not in row["score"]:
            raise ValueError(f"{entity} must contain score.score")
        if not isinstance(row["market"], dict) or "volatility_20d" not in row["market"]:
            raise ValueError(f"{entity} must contain market.volatility_20d")
        if row["score"]["score"] is not None:
            _number(row["score"]["score"], f"{entity}.score")
        vol = row["market"]["volatility_20d"]
        if vol is not None and _number(vol, f"{entity}.volatility_20d") < 0:
            raise ValueError("volatility_20d cannot be negative")
        evidence = row["evidence_ids"]
        if not isinstance(evidence, (list, tuple)) or any(not isinstance(e, str) for e in evidence):
            raise ValueError("evidence_ids must be a list of strings")
        row_map[entity] = row
    ids = [_entity_id(entity) for entity in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("selected contains duplicate entity IDs")
    if any(entity not in row_map for entity in ids):
        raise ValueError("each selected entity must have a corresponding row")
    return ids, row_map


def _allocate_with_cap(
    raw: dict[str, float], cap: float, inverse: bool = False,
) -> tuple[dict[str, float], list[str]]:
    """Capped proportional allocation; if cap cannot fill NAV, preserve cash."""
    weights = dict.fromkeys(raw, 0.0)
    free = [entity for entity, value in raw.items() if value > 0]
    if not free:
        return weights, []
    # A hard cap is never relaxed. If there is not enough eligible capacity,
    # every positive name receives cap and residual remains cash.
    capacity = len(free) * cap
    if capacity <= 1.0 + 1e-12:
        for entity in free:
            weights[entity] = cap
        return weights, free
    locked: list[str] = []
    while free:
        remaining = max(0.0, 1.0 - math.fsum(weights[entity] for entity in locked))
        scale = (min if inverse else max)(raw[entity] for entity in free)
        ratios = {entity: scale / raw[entity] if inverse else raw[entity] / scale for entity in free}
        total = math.fsum(ratios.values())
        proposed = {entity: remaining * ratios[entity] / total for entity in free}
        over = [entity for entity in free if proposed[entity] > cap + 1e-12]
        if not over:
            weights.update(proposed)
            break
        for entity in over:
            weights[entity] = cap
        locked.extend(over)
        free = [entity for entity in free if entity not in over]
    invested = math.fsum(weights.values())
    if invested > 1.0 + 1e-12:
        largest = max(weights, key=weights.get)
        weights[largest] -= invested - 1.0
    return weights, locked


def build_portfolio(
    screen_result: dict[str, Any], method: str = "equal", max_names: int = 5,
    min_names: int = 1, weight_cap: float = 0.30,
) -> dict[str, Any]:
    """Use selected IDs in their supplied order; do not select replacement names.

    Zero/nonpositive scores get zero score-weighted exposure. Missing or zero
    volatility gets zero inverse-vol exposure (no imputation). All selected
    names, including zero-weight names, remain in holdings. min_names counts
    selected names, not positive allocations. Cash-only allocation is valid.
    """
    if not isinstance(method, str) or method not in {"equal", "score_weighted", "vol_inverse"}:
        raise ValueError("method must be equal, score_weighted, or vol_inverse")
    max_names = _positive_integer(max_names, "max_names")
    min_names = _positive_integer(min_names, "min_names")
    if min_names > max_names:
        raise ValueError("min_names cannot exceed max_names")
    cap = _number(weight_cap, "weight_cap")
    if not 0 < cap <= 1:
        raise ValueError("weight_cap must be in (0, 1]")
    ids, rows = _screen_rows(screen_result)
    ids = ids[:max_names]
    constraints = ["long_only", "selected_top_max_names", f"weight_cap_{cap:.0%}"]
    result: dict[str, Any] = {
        "status": "insufficient", "method": method, "holdings": [],
        "weights_sum": 0.0, "cash_weight": 1.0, "constraints_applied": constraints,
        "formula_refs": [
            "equal: raw_i=1", "score_weighted: raw_i=max(score_i,0)",
            "vol_inverse: raw_i=1/vol_i only for observed positive volatility",
            "capped proportional allocation: 0 <= w_i <= cap; cash=1-sum(w_i)",
        ],
        "caveat": "Deterministic long-only heuristic; no optimiser, expected-return forecast, or guarantee of optimality.",
    }
    if len(ids) < min_names:
        constraints.append(f"need_at_least_{min_names}_names")
        return result
    raw = {}
    for entity in ids:
        row = rows[entity]
        if method == "equal":
            raw[entity] = 1.0
        elif method == "score_weighted":
            score = row["score"]["score"]
            raw[entity] = max(0.0, float(score)) if score is not None else 0.0
            if raw[entity] == 0:
                constraints.append(f"nonpositive_or_missing_score_zero_weight:{entity}")
        else:
            vol = row["market"]["volatility_20d"]
            raw[entity] = float(vol) if vol is not None else 0.0
            if raw[entity] == 0:
                constraints.append(f"missing_or_zero_volatility_zero_weight:{entity}")
    weights, capped = _allocate_with_cap(raw, cap, inverse=method == "vol_inverse")
    invested = math.fsum(weights.values())
    if capped:
        constraints.append("capped:" + ",".join(capped))
    if invested < 1.0:
        constraints.append("residual_cash_preserved")
    if invested == 0:
        constraints.append("all_raw_weights_zero_cash_only")
    result.update({
        "status": "valid", "weights_sum": invested, "cash_weight": max(0.0, 1.0 - invested),
        "holdings": [{
            "entity_id": entity, "sector": rows[entity]["sector"], "weight": weights[entity],
            "raw_score": rows[entity]["score"]["score"],
            "volatility_20d": rows[entity]["market"]["volatility_20d"],
            "rationale": "screen-selected order; explicit weighting rule and hard cap",
            "evidence_ids": list(rows[entity]["evidence_ids"]),
        } for entity in ids],
    })
    return result


def _holdings(holdings: Any) -> tuple[list[str], np.ndarray, dict[str, float]]:
    if not isinstance(holdings, (list, tuple)):
        raise ValueError("holdings must be a list")
    ids, values = [], []
    sectors: dict[str, float] = {}
    for holding in holdings:
        if not isinstance(holding, dict) or not {"entity_id", "weight"} <= holding.keys():
            raise ValueError("each holding must contain entity_id and weight")
        entity = _entity_id(holding["entity_id"])
        if entity in ids:
            raise ValueError(f"duplicate holding: {entity}")
        weight = _number(holding["weight"], f"{entity}.weight")
        if not 0 <= weight <= 1:
            raise ValueError("long-only holding weights must be in [0, 1]")
        sector = holding.get("sector", "Unknown")
        if not isinstance(sector, str):
            raise ValueError("holding sector must be a string")
        ids.append(entity)
        values.append(weight)
        sectors[sector] = sectors.get(sector, 0.0) + weight
    if math.fsum(values) > 1.0 + 1e-12:
        raise ValueError("sum of holding weights cannot exceed 1")
    return ids, np.asarray(values, dtype=float), sectors


def _date(value: Any, name: str) -> pd.Timestamp:
    if isinstance(value, (Real, bool, np.bool_)) or value is None:
        raise ValueError(f"{name} must be a calendar date")
    try:
        date = pd.to_datetime(value, utc=True, errors="raise")
        if not isinstance(date, pd.Timestamp) or pd.isna(date):
            raise ValueError("missing date")
        return date.tz_localize(None).normalize()
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{name} must be a calendar date") from exc


def _scenarios(scenarios: Any, count: int) -> list[dict[str, Any]]:
    if scenarios is None:
        scenarios = _DEFAULT_SCENARIOS
    if not isinstance(scenarios, (list, tuple)):
        raise ValueError("scenarios must be a list or None")
    result, names = [], set()
    for item in scenarios:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("each scenario must have a non-empty name")
        name, typ = item["name"], item.get("type")
        if name in names:
            raise ValueError("scenario names must be unique")
        names.add(name)
        if not isinstance(typ, str) or typ not in _HISTORICAL_TYPES | {"parametric", "correlation"}:
            raise ValueError(f"unknown scenario type: {typ}")
        scenario = dict(item)
        allowed = {"name", "type"}
        if typ in _HISTORICAL_TYPES:
            allowed |= {"window", "start_date", "end_date"}
            if "start_date" in item or "end_date" in item:
                if typ == "historical" or "window" in item or not {"start_date", "end_date"} <= item.keys():
                    raise ValueError("dated historical_replay needs both start_date and end_date, without window")
                start = _date(item["start_date"], "start_date")
                end = _date(item["end_date"], "end_date")
                if start >= end:
                    raise ValueError("historical replay start_date must precede end_date")
                scenario.update(start_date=start, end_date=end)
            else:
                scenario["window"] = _positive_integer(item.get("window", 20), "window")
        else:
            allowed |= {"z", "horizon"}
            scenario["z"] = _number(item.get("z", _DEFAULT_Z), "z")
            if scenario["z"] <= 0:
                raise ValueError("z must be positive")
            if _positive_integer(item.get("horizon", 1), "horizon") != 1:
                raise ValueError("parametric/correlation stress supports only a 1-day horizon")
            if typ == "correlation":
                allowed.add("rho")
                rho = _number(item.get("rho", 0.95), "rho")
                lower = -1.0 / (count - 1) if count > 1 else -1.0
                if not lower <= rho <= 1:
                    raise ValueError(f"rho must be in [{lower:g}, 1] for a positive-semidefinite correlation matrix")
                scenario["rho"] = rho
        if set(item) - allowed:
            raise ValueError(f"unknown parameters in scenario {name}: {sorted(set(item) - allowed)}")
        result.append(scenario)
    return result


def _prices(entity: str, frame: Any, warnings: list[str]) -> pd.Series:
    if not isinstance(frame, pd.DataFrame):
        raise ValueError(f"market frame for {entity} must be a DataFrame")
    if frame.empty:
        return pd.Series(index=pd.DatetimeIndex([]), dtype=float, name=entity)
    if frame.columns.has_duplicates or "close" not in frame:
        raise ValueError(f"{entity}: market frame needs unique columns including close")
    if "date" in frame:
        raw_dates = frame["date"]
    elif isinstance(frame.index, pd.DatetimeIndex):
        raw_dates = frame.index
    else:
        raise ValueError(f"{entity}: provide a date column or DatetimeIndex")
    dates = pd.DatetimeIndex([_date(value, f"{entity}.date") for value in raw_dates])
    if dates.has_duplicates:
        raise ValueError(f"{entity}: duplicate calendar dates")
    # Missing observations are excluded, never filled. Bad/nonpositive prices
    # are input errors rather than zero returns or plausible-looking prices.
    closes = []
    for close in frame["close"]:
        if close is None or close is pd.NA or (isinstance(close, Real) and math.isnan(float(close))):
            closes.append(np.nan)
        else:
            value = _number(close, f"{entity}.close")
            if value <= 0:
                raise ValueError(f"{entity}: close prices must be positive")
            closes.append(value)
    series = pd.Series(closes, index=dates, name=entity, dtype=float).sort_index()
    missing = int(series.isna().sum())
    if missing:
        warnings.append(f"{entity}: {missing} missing prices excluded; no filling")
    return series.dropna()


def _gap_warning(index: pd.DatetimeIndex, label: str, warnings: list[str]) -> None:
    if len(index) > 1:
        gap = int(index.to_series().diff().dt.days.max())
        if gap > 7:
            warnings.append(f"{label}: price gap exceeds 7 days ({gap} days); daily-horizon estimate may be unreliable")


def _historical(
    scenario: dict[str, Any], prices: pd.DataFrame, returns: pd.DataFrame,
    weights: np.ndarray, ids: list[str],
) -> dict[str, Any]:
    """Signed loss and chain-linked attribution on one actual date interval."""
    matrix = returns.to_numpy(dtype=float)
    daily = matrix @ weights
    count = len(returns)
    if "start_date" in scenario:
        start, end = scenario["start_date"], scenario["end_date"]
        if start not in prices.index or end not in prices.index:
            return {"status": "insufficient", "assumptions": ["replay boundaries must be observed common price dates"]}
        first, stop = int(prices.index.get_loc(start)), int(prices.index.get_loc(end))
        window = stop - first
    else:
        window = scenario["window"]
        if window > count:
            return {"status": "insufficient", "assumptions": ["not enough joint returns for requested window"]}
        if scenario["type"] == "historical":
            with np.errstate(over="ignore", invalid="ignore"):
                rolling = pd.Series(1.0 + daily).rolling(window).apply(np.prod, raw=True).iloc[window - 1:]
            if not np.isfinite(rolling.to_numpy()).all():
                raise ValueError("historical compounded returns exceed finite numeric range")
            first = int(np.argmin(rolling.to_numpy()))
            stop = first + window
        else:
            first, stop = count - window, count
    interval, portfolio = matrix[first:stop], daily[first:stop]
    with np.errstate(over="ignore", invalid="ignore"):
        wealth = np.cumprod(1.0 + portfolio)
        entering_wealth = np.r_[1.0, wealth[:-1]]
        contribution = -np.sum(entering_wealth[:, None] * interval * weights, axis=0)
        asset_returns = np.prod(1.0 + interval, axis=0) - 1.0
    if not np.isfinite(wealth).all() or not np.isfinite(contribution).all() or not np.isfinite(asset_returns).all():
        raise ValueError("historical replay exceeds finite numeric range")
    pnl = float(wealth[-1] - 1.0)
    return {
        "status": "valid", "portfolio_loss": -pnl, "portfolio_return": pnl,
        "per_entity_contribution": dict(zip(ids, map(float, contribution))),
        "window_start": prices.index[first].date().isoformat(),
        "window_end": prices.index[stop].date().isoformat(),
        "first_return_date": returns.index[first].date().isoformat(),
        "horizon_days": window, "horizon_label": f"{window}-day",
        "risk_horizon_label": f"{window}-observation historical replay",
        "interval_returns": dict(zip(ids, map(float, asset_returns))),
        "window_selection": "worst" if scenario["type"] == "historical" else "fixed_interval",
        "assumptions": [
            "fixed current weights applied each day to all assets over the same actual-date interval",
            "compound daily portfolio returns; cash earns zero; contributions are chain-linked",
            "historical replay is a risk diagnostic, not a tradable backtest; no costs or trading feasibility model",
            "portfolio_loss is signed: positive means loss, negative means gain",
        ],
        **({"worst_window_return": pnl} if scenario["type"] == "historical" else {}),
    }


def portfolio_stress(
    holdings: list[dict[str, Any]], market_frames: dict[str, pd.DataFrame],
    scenarios: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Stress positive exposures using >=40 truly overlapping daily returns.

    Common valid prices are intersected FIRST, then returns are calculated, so
    each asset has the same start/end dates for every return. Missing prices
    are never forward-filled. Dates represent UTC calendar dates.

    Defaults retain the three legacy scenario names. ``historical`` selects
    the worst rolling window (default 20). ``historical_replay`` (alias
    ``historical_fixed_weight``) replays start_date/end_date inclusive price
    boundaries, or the latest window if no dates are supplied. Both historical
    types use fixed current weights and are risk diagnostics, not backtests.
    """
    all_ids, all_weights, sectors = _holdings(holdings)
    active = all_weights > 0
    ids = [entity for entity, keep in zip(all_ids, active) if keep]
    weights = all_weights[active]
    if not isinstance(market_frames, dict):
        raise ValueError("market_frames must be a mapping")
    definitions = _scenarios(scenarios, len(ids))
    invested = math.fsum(all_weights)
    cash = max(0.0, 1.0 - invested)
    warnings: list[str] = []
    result: dict[str, Any] = {
        "status": "insufficient", "scenarios": [], "warnings": warnings,
        "observations": {}, "joint_price_observations": 0, "joint_return_observations": 0,
        "invested_weight": invested, "cash_weight": cash, "sector_weights": sectors,
        "hhi": float(all_weights @ all_weights), "sector_hhi": math.fsum(w * w for w in sectors.values()),
        "hhi_basis": "squared NAV weights excluding cash, not renormalised to invested assets",
        "risk_horizon_labels": {},
        "formula_refs": [
            "parametric_loss = z * sqrt(w' cov_daily w); sample covariance ddof=1; zero mean",
            "correlation stress replaces off-diagonal rho using common-date daily volatilities",
            "historical portfolio_loss = 1 - product_t(1 + sum_i(w_i*r_i,t))",
        ],
        "caveat": "Current-weight risk diagnostics only; not calibrated VaR, investment forecasts, or tradable backtests. Cash earns zero.",
    }
    if not ids:
        warnings.append("no positive-weight holdings; no risky-asset stress is estimable")
        return result
    missing = False
    series = []
    for entity in ids:
        if entity not in market_frames:
            warnings.append(f"{entity}: missing market frame; fewer than 40 price observations")
            prices = pd.Series(index=pd.DatetimeIndex([]), dtype=float, name=entity)
            missing = True
        else:
            prices = _prices(entity, market_frames[entity], warnings)
        result["observations"][entity] = len(prices)
        if len(prices) < 40:
            warnings.append(f"{entity}: fewer than 40 price observations ({len(prices)})")
        _gap_warning(prices.index, entity, warnings)
        series.append(prices)
    common = pd.concat(series, axis=1, join="inner").sort_index()
    _gap_warning(common.index, "common price grid", warnings)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        returns = common.pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(returns.to_numpy()).all():
        raise ValueError("common-date returns exceed finite numeric range")
    returns = returns.dropna(how="any")
    result.update(joint_price_observations=len(common), joint_return_observations=len(returns))
    if len(common):
        result.update(common_price_start=common.index[0].date().isoformat(), common_price_end=common.index[-1].date().isoformat())
    if len(returns):
        result.update(common_return_start=returns.index[0].date().isoformat(), common_return_end=returns.index[-1].date().isoformat())
    if len(returns) < 40:
        warnings.append(f"need at least 40 joint returns; observed {len(returns)}")
    for scenario in definitions:
        typ = scenario["type"]
        horizon = scenario.get("window") if typ in _HISTORICAL_TYPES else 1
        out: dict[str, Any] = {
            "name": scenario["name"], "type": typ, "status": "insufficient",
            "portfolio_loss": None, "per_entity_contribution": None,
            "horizon_days": horizon, "horizon_label": f"{horizon}-day" if horizon else "dated interval",
            "assumptions": ["need at least 40 overlapping daily returns"],
        }
        if len(returns) >= 40 and not missing:
            if typ in _HISTORICAL_TYPES:
                out.update(_historical(scenario, common, returns, weights, ids))
            else:
                with np.errstate(over="ignore", invalid="ignore"):
                    covariance = returns.cov(ddof=1).to_numpy()
                    if typ == "correlation":
                        vol = returns.std(ddof=1).to_numpy()
                        correlation = np.full((len(ids), len(ids)), scenario["rho"])
                        np.fill_diagonal(correlation, 1.0)
                        covariance = np.outer(vol, vol) * correlation
                    variance = float(weights @ covariance @ weights)
                if not np.isfinite(covariance).all() or not math.isfinite(variance):
                    raise ValueError("daily covariance exceeds finite numeric range")
                volatility = math.sqrt(max(0.0, variance))
                z = scenario["z"]
                contribution = z * weights * (covariance @ weights) / volatility if volatility > 0 else np.zeros_like(weights)
                loss = z * volatility
                if not math.isfinite(loss) or not np.isfinite(contribution).all():
                    raise ValueError("parametric loss exceeds finite numeric range")
                out.update({
                    "status": "valid", "portfolio_loss": loss,
                    "per_entity_contribution": dict(zip(ids, map(float, contribution))),
                    "z": z, "portfolio_daily_volatility": volatility,
                    "daily_covariance": covariance.tolist(), "covariance_entity_ids": ids,
                    "risk_horizon_label": "1-day", "mean_assumption": "zero",
                    "assumptions": ["zero-mean normal one-day loss; no annualisation", "sample daily covariance on common price intervals; cash earns zero"],
                })
                if typ == "correlation":
                    out["rho"] = scenario["rho"]
                    out["assumptions"].append(f"off-diagonal correlation rho={scenario['rho']:g}")
            if out["status"] == "valid":
                contributions = out["per_entity_contribution"]
                out["per_entity_contribution"] = {entity: contributions.get(entity, 0.0) for entity in all_ids}
        out["risk_contributions"] = out["per_entity_contribution"]
        result["scenarios"].append(out)
        result["risk_horizon_labels"][out["name"]] = out.get("risk_horizon_label", out["horizon_label"])
    result["status"] = "valid" if any(item["status"] == "valid" for item in result["scenarios"]) else "insufficient"
    return result

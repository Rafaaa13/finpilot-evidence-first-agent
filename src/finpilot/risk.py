from __future__ import annotations

"""Offline credit, fixed-income, and option risk lab.

Everything here is synthetic and educational.  The credit portfolio is a
reproducible 240-loan sample with a chronological train/validation split; it
is useful for testing plumbing and metric calculations, not for IFRS 9,
capital, pricing, or regulatory validation.
"""

import datetime as dt
import math
from statistics import NormalDist
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


TRAIN_START_MONTH = "2023-01"
TRAIN_END_MONTH = "2023-12"
VALIDATION_START_MONTH = "2024-01"
VALIDATION_END_MONTH = "2024-12"


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _clip(value: Any, low: float, high: float) -> float:
    number = _finite(value)
    if number is None:
        number = low
    return float(min(high, max(low, number)))


def _month_add(year: int, month: int, offset: int) -> tuple[int, int]:
    absolute = year * 12 + (month - 1) + offset
    return absolute // 12, absolute % 12 + 1


def _loan_rows(loans: Sequence[dict[str, Any]] | pd.DataFrame | Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(loans, pd.DataFrame):
        return loans.to_dict(orient="records")
    return [dict(row) for row in loans]


def synthetic_loans(seed: int = 42, n_loans: int = 240) -> list[dict[str, Any]]:
    """Generate the fixed-shape synthetic portfolio used by ``run_risk_lab``."""
    if n_loans != 240:
        raise ValueError("the educational fixture is intentionally fixed at 240 loans")
    rng = np.random.default_rng(int(seed))
    loans: list[dict[str, Any]] = []
    for index in range(n_loans):
        month_index = index // 10
        year, month_number = _month_add(2023, 1, month_index)
        month = f"{year:04d}-{month_number:02d}"
        month_end = (dt.date(year + (month_number == 12), 1 if month_number == 12 else month_number + 1, 1) - dt.timedelta(days=1)).isoformat()
        # These deterministic bands create variation without pretending to
        # represent a real lender's portfolio or a calibrated PD model.
        predicted_pd = _clip(0.025 + 0.005 * (index % 8) + 0.003 * (month_index % 6), 0.01, 0.25)
        lgd = _clip(0.35 + 0.025 * (index % 6), 0.0, 1.0)
        ead = float(50_000 + 4_000 * (index % 12) + 1_500 * (month_index % 4))
        realized_default = int(rng.binomial(1, predicted_pd))
        loans.append(
            {
                "loan_id": f"SYN-{index + 1:03d}",
                "month": month,
                "month_end": month_end,
                "pd": float(predicted_pd),
                "predicted_pd": float(predicted_pd),
                "lgd": float(lgd),
                "ead": ead,
                "default": realized_default,
                "realized_default": realized_default,
            }
        )
    return loans


def _auc(y_true: Sequence[int], scores: Sequence[float]) -> float | None:
    """A tie-aware AUC using average ranks, with no sklearn dependency."""
    y = np.asarray(y_true, dtype=int)
    s = np.asarray(scores, dtype=float)
    if len(y) == 0 or len(y) != len(s):
        return None
    positives = y == 1
    negatives = y == 0
    n_positive = int(positives.sum())
    n_negative = int(negatives.sum())
    if n_positive == 0 or n_negative == 0:
        return None
    order = np.argsort(s, kind="mergesort")
    sorted_scores = s[order]
    ranks = np.empty(len(s), dtype=float)
    start = 0
    while start < len(s):
        stop = start + 1
        while stop < len(s) and sorted_scores[stop] == sorted_scores[start]:
            stop += 1
        ranks[order[start:stop]] = (start + 1 + stop) / 2.0
        start = stop
    positive_rank_sum = ranks[positives].sum()
    return _finite((positive_rank_sum - n_positive * (n_positive + 1) / 2.0) / (n_positive * n_negative))


def _ece(y_true: Sequence[int], probabilities: Sequence[float], bins: int = 10) -> float | None:
    if not y_true:
        return None
    y = np.asarray(y_true, dtype=float)
    p = np.clip(np.asarray(probabilities, dtype=float), 0.0, 1.0)
    if len(y) != len(p):
        return None
    total = len(y)
    error = 0.0
    for bucket in range(bins):
        lower = bucket / bins
        upper = (bucket + 1) / bins
        mask = (p >= lower) & (p < upper if bucket < bins - 1 else p <= upper)
        if mask.any():
            error += float(mask.sum()) / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return _finite(error)


def _classification_metrics(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    labels = [int(row.get("default", row.get("realized_default", 0))) for row in rows]
    probabilities = [_clip(row.get("predicted_pd", row.get("pd", 0.0)), 0.0, 1.0) for row in rows]
    if not labels:
        return {"n": 0, "default_rate": None, "predicted_pd_mean": None, "auc": None, "brier": None, "ece": None}
    y = np.asarray(labels, dtype=float)
    p = np.asarray(probabilities, dtype=float)
    return {
        "n": int(len(labels)),
        "default_rate": _finite(y.mean()),
        "predicted_pd_mean": _finite(p.mean()),
        "auc": _auc(labels, probabilities),
        "brier": _finite(np.mean((p - y) ** 2)),
        "ece": _ece(labels, probabilities),
        "ece_bins": 10,
    }


def _ead_concentration(rows: Sequence[dict[str, Any]]) -> dict[str, float | None]:
    ead = np.asarray([max(0.0, float(row.get("ead", 0.0))) for row in rows], dtype=float)
    total = float(ead.sum())
    if total <= 0:
        return {"total_ead": 0.0, "top_1_share": None, "top_5_share": None, "top_10pct_share": None, "hhi": None}
    shares = np.sort(ead / total)[::-1]
    top_n = max(1, int(math.ceil(len(shares) * 0.10)))
    return {
        "total_ead": _finite(total),
        "top_1_share": _finite(shares[:1].sum()),
        "top_5_share": _finite(shares[:5].sum()),
        "top_10pct_share": _finite(shares[:top_n].sum()),
        "hhi": _finite(np.square(shares).sum()),
    }


def credit_losses(
    loans: Sequence[dict[str, Any]] | pd.DataFrame | Iterable[dict[str, Any]],
    pd_multiplier: float = 1.0,
    lgd_shift: float = 0.0,
) -> dict[str, Any]:
    """Calculate exposure-weighted expected loss under a transparent stress.

    ``expected_loss_rate`` is ``sum(EAD * stressed_PD * stressed_LGD) /
    sum(EAD)``.  It is intentionally not an unweighted average of PDs.
    """
    if not math.isfinite(float(pd_multiplier)) or pd_multiplier < 0:
        raise ValueError("pd_multiplier must be finite and non-negative")
    if not math.isfinite(float(lgd_shift)):
        raise ValueError("lgd_shift must be finite")
    rows = _loan_rows(loans)
    enriched: list[dict[str, Any]] = []
    total_ead = 0.0
    expected_loss_amount = 0.0
    realized_loss_amount = 0.0
    for row in rows:
        for key in ('ead', 'lgd'):
            if key not in row or _finite(row[key]) is None:
                raise ValueError(f'missing/nonfinite loan {key}')
        raw_pd = row.get('predicted_pd', row.get('pd'))
        if _finite(raw_pd) is None or not 0 <= float(raw_pd) <= 1 or not 0 <= float(row['lgd']) <= 1 or float(row['ead']) < 0:
            raise ValueError('invalid base loan parameters')
        ead = float(row['ead'])
        pd_value = _clip(row.get("predicted_pd", row.get("pd", 0.0)), 0.0, 1.0)
        lgd_value = _clip(row.get("lgd", 0.0), 0.0, 1.0)
        stressed_pd = _clip(pd_value * float(pd_multiplier), 0.0, 1.0)
        stressed_lgd = _clip(lgd_value + float(lgd_shift), 0.0, 1.0)
        expected_loss = ead * stressed_pd * stressed_lgd
        default = int(row.get("default", row.get("realized_default", 0)))
        realized_loss = ead * default * stressed_lgd
        total_ead += ead
        expected_loss_amount += expected_loss
        realized_loss_amount += realized_loss
        copy = dict(row)
        copy.update(
            {
                "stressed_pd": _finite(stressed_pd),
                "stressed_lgd": _finite(stressed_lgd),
                "expected_loss": _finite(expected_loss),
                "realized_loss_under_stressed_lgd": _finite(realized_loss),
            }
        )
        enriched.append(copy)
    return {
        "status": "valid" if rows and total_ead > 0 else "missing",
        "pd_multiplier": float(pd_multiplier),
        "lgd_shift": float(lgd_shift),
        "pd_cap": [0.0, 1.0],
        "lgd_cap": [0.0, 1.0],
        "loan_count": int(len(rows)),
        "total_ead": _finite(total_ead),
        "expected_loss_amount": _finite(expected_loss_amount),
        "expected_loss_rate": _finite(expected_loss_amount / total_ead) if total_ead > 0 else None,
        "realized_loss_amount": _finite(realized_loss_amount),
        "realized_loss_rate": _finite(realized_loss_amount / total_ead) if total_ead > 0 else None,
        "ead_concentration": _ead_concentration(rows),
        "loan_losses": enriched,
        "formula": "EL = sum(EAD_i * clip(PD_i * multiplier, 0, 1) * clip(LGD_i + shift, 0, 1)); EL_rate = EL / sum(EAD_i)",
    }


def run_risk_lab(pd_multiplier: float = 1.5, lgd_shift: float = 0.10, seed: int = 42) -> dict[str, Any]:
    """Run the reproducible synthetic credit and fixed-income risk lab."""
    loans = synthetic_loans(seed=seed)
    baseline = credit_losses(loans, pd_multiplier=1.0, lgd_shift=0.0)
    stressed = credit_losses(loans, pd_multiplier=pd_multiplier, lgd_shift=lgd_shift)
    train = [row for row in loans if TRAIN_START_MONTH <= str(row["month"]) <= TRAIN_END_MONTH]
    validation = [row for row in loans if VALIDATION_START_MONTH <= str(row["month"]) <= VALIDATION_END_MONTH]
    train_metrics = _classification_metrics(train)
    validation_metrics = _classification_metrics(validation)
    overall_metrics = _classification_metrics(loans)
    concentration = _ead_concentration(loans)

    segments = {
        "train": {
            "start_month": TRAIN_START_MONTH,
            "end_month": TRAIN_END_MONTH,
            "count": len(train),
            "metrics": train_metrics,
        },
        "validation": {
            "start_month": VALIDATION_START_MONTH,
            "end_month": VALIDATION_END_MONTH,
            "count": len(validation),
            "metrics": validation_metrics,
        },
    }
    validation_report = {
        "split": "immutable chronological split",
        "train_period": {"start": TRAIN_START_MONTH, "end": TRAIN_END_MONTH, "count": len(train)},
        "validation_period": {"start": VALIDATION_START_MONTH, "end": VALIDATION_END_MONTH, "count": len(validation)},
        "train": train_metrics,
        "validation": validation_metrics,
        "overall": overall_metrics,
        "caveat": "AUC, Brier and 10-bin ECE are calculated on synthetic sampled defaults; this is not true calibration, IFRS 9 validation, or regulatory validation.",
    }
    summary = {
        "status": "valid",
        "seed": int(seed),
        "loan_count": len(loans),
        "train_count": len(train),
        "validation_count": len(validation),
        "total_ead": concentration["total_ead"],
        "baseline_expected_loss_amount": baseline["expected_loss_amount"],
        "baseline_expected_loss_rate": baseline["expected_loss_rate"],
        "stressed_expected_loss_amount": stressed["expected_loss_amount"],
        "stressed_expected_loss_rate": stressed["expected_loss_rate"],
        "realized_default_rate": overall_metrics["default_rate"],
        "ead_concentration": concentration,
        "caveat": "Synthetic educational portfolio only; no claim of real borrower behavior, calibration, IFRS 9 compliance, capital adequacy, or regulatory validation.",
    }
    stress = {
        "pd_multiplier": float(pd_multiplier),
        "lgd_shift": float(lgd_shift),
        "baseline": {
            "expected_loss_amount": baseline["expected_loss_amount"],
            "expected_loss_rate": baseline["expected_loss_rate"],
        },
        "stressed": {
            "expected_loss_amount": stressed["expected_loss_amount"],
            "expected_loss_rate": stressed["expected_loss_rate"],
        },
        "incremental_expected_loss_amount": _finite(stressed["expected_loss_amount"] - baseline["expected_loss_amount"]),
        "incremental_expected_loss_rate": _finite(stressed["expected_loss_rate"] - baseline["expected_loss_rate"]),
        "pd_cap": [0.0, 1.0],
        "lgd_cap": [0.0, 1.0],
    }
    return {
        "summary": summary,
        "segments": segments,
        "stress": stress,
        "validation": validation_report,
        "loans": loans,
    }


def _bond_inputs(face: float, coupon_rate: float, yield_rate: float, years: float, frequency: int) -> tuple[float, float, float, float, int]:
    face_value = float(face)
    coupon = float(coupon_rate)
    y = float(yield_rate)
    term = float(years)
    if not all(math.isfinite(x) for x in (face_value, coupon, y, term)) or face_value <= 0 or term <= 0:
        raise ValueError("face and years must be positive finite values")
    if not isinstance(frequency, (int, np.integer)) or frequency <= 0:
        raise ValueError("frequency must be a positive integer")
    periods_float = term * int(frequency)
    periods = int(round(periods_float))
    if abs(periods_float - periods) > 1e-9:
        raise ValueError("years * frequency must be an integer for this periodic-coupon model")
    if 1.0 + y / int(frequency) <= 0:
        raise ValueError("yield creates a non-positive discount denominator")
    return face_value, coupon, y, term, periods


def bond_price(face: float, coupon_rate: float, yield_rate: float, years: float, frequency: int = 2) -> float:
    """Present value of a periodic-coupon bond, with rates as decimals."""
    face_value, coupon, y, _term, periods = _bond_inputs(face, coupon_rate, yield_rate, years, frequency)
    freq = int(frequency)
    discount = 1.0 + y / freq
    coupon_payment = face_value * coupon / freq
    price = sum(coupon_payment / discount**period for period in range(1, periods + 1)) + face_value / discount**periods
    return float(price)


def bond_risk(
    face: float,
    coupon_rate: float,
    yield_rate: float,
    years: float,
    frequency: int = 2,
    shock_bps: float = 100.0,
    bps_shock: float | None = None,
) -> dict[str, Any]:
    """Return price, duration, convexity, DV01, and a parallel-yield scenario."""
    if bps_shock is not None:
        shock_bps = bps_shock
    if not math.isfinite(float(shock_bps)):
        raise ValueError("shock_bps must be finite")
    face_value, coupon, y, term, periods = _bond_inputs(face, coupon_rate, yield_rate, years, frequency)
    freq = int(frequency)
    discount = 1.0 + y / freq
    coupon_payment = face_value * coupon / freq
    cash_flows: list[tuple[float, float, int]] = []
    for period in range(1, periods + 1):
        cash_flow = coupon_payment + (face_value if period == periods else 0.0)
        cash_flows.append((period / freq, cash_flow, period))
    price = sum(cash_flow / discount**period for _time, cash_flow, period in cash_flows)
    pv_weights = [cash_flow / discount**period for _time, cash_flow, period in cash_flows]
    macaulay = sum(time * pv for (time, _cash_flow, _period), pv in zip(cash_flows, pv_weights)) / price
    modified_duration = macaulay / discount
    convexity = sum(time * (time + 1.0 / freq) * pv for (time, _cash_flow, _period), pv in zip(cash_flows, pv_weights)) / (price * discount**2)
    one_bp_price = bond_price(face_value, coupon, y + 0.0001, term, freq)
    dv01 = price - one_bp_price
    shock_decimal = float(shock_bps) / 10_000.0
    shocked_yield = y + shock_decimal
    shocked_price = bond_price(face_value, coupon, shocked_yield, term, freq)
    duration_approx = -modified_duration * price * shock_decimal
    convexity_approx = duration_approx + 0.5 * convexity * price * shock_decimal**2
    return {
        "price": _finite(price),
        "modified_duration": _finite(modified_duration),
        "macaulay_duration": _finite(macaulay),
        "convexity": _finite(convexity),
        "dv01": _finite(dv01),
        "scenario": {
            "shock_bps": _finite(shock_bps),
            "shocked_yield": _finite(shocked_yield),
            "shocked_price": _finite(shocked_price),
            "price_change": _finite(shocked_price - price),
            "price_change_pct": _finite(shocked_price / price - 1.0),
            "duration_approx_price_change": _finite(duration_approx),
            "duration_convexity_approx_price_change": _finite(convexity_approx),
        },
        "formula_refs": [
            "modified_duration = Macaulay_duration / (1 + yield/frequency)",
            "convexity = sum(PV(CF_t) * t * (t + 1/frequency)) / (price * (1 + yield/frequency)^2)",
            "DV01 = price(y) - price(y + 1bp)",
        ],
    }


def black_scholes_price(
    spot: float,
    strike: float,
    risk_free_rate: float,
    volatility: float,
    time_to_expiry: float,
    option_type: str = "call",
    dividend_yield: float = 0.0,
) -> float:
    """Analytic Black-Scholes price for a European call or put."""
    s, k, r, sigma, t, q = map(float, (spot, strike, risk_free_rate, volatility, time_to_expiry, dividend_yield))
    kind = option_type.lower()
    if not all(math.isfinite(v) for v in (s,k,r,sigma,t,q)) or s <= 0 or k <= 0 or sigma < 0 or t < 0 or kind not in {"call", "put"}:
        raise ValueError("invalid Black-Scholes input")
    if t == 0 or sigma == 0:
        forward = s * math.exp(-q * t) - k * math.exp(-r * t)
        return float(max(forward, 0.0) if kind == "call" else max(-forward, 0.0))
    root_t = math.sqrt(t)
    d1 = (math.log(s / k) + (r - q + 0.5 * sigma**2) * t) / (sigma * root_t)
    d2 = d1 - sigma * root_t
    normal = NormalDist().cdf
    call = s * math.exp(-q * t) * normal(d1) - k * math.exp(-r * t) * normal(d2)
    return float(call if kind == "call" else call - s * math.exp(-q * t) + k * math.exp(-r * t))


def option_price(
    spot: float,
    strike: float,
    risk_free_rate: float,
    volatility: float,
    time_to_expiry: float,
    option_type: str = "call",
    dividend_yield: float = 0.0,
    simulations: int = 0,
    seed: int = 42,
) -> dict[str, Any]:
    """Return analytic BS price and, optionally, a seeded MC estimate/standard error."""
    analytic = black_scholes_price(spot, strike, risk_free_rate, volatility, time_to_expiry, option_type, dividend_yield)
    result: dict[str, Any] = {
        "status": "valid",
        "option_type": option_type.lower(),
        "black_scholes": _finite(analytic),
        "monte_carlo": None,
        "standard_error": None,
        "put_call_parity_residual": None,
        "caveat": "European Black-Scholes assumptions; Monte Carlo is a numerical check, not a calibration or valuation opinion.",
    }
    if not isinstance(simulations, int) or simulations < 0 or simulations > 1000000:
        raise ValueError('simulations must be an integer in [0, 1000000]')
    if simulations and simulations > 0:
        if simulations < 2:
            raise ValueError("simulations must be zero or at least two")
        rng = np.random.default_rng(int(seed))
        spot_value = float(spot)
        strike_value = float(strike)
        r = float(risk_free_rate)
        q = float(dividend_yield)
        sigma = float(volatility)
        t = float(time_to_expiry)
        terminal = spot_value * np.exp((r - q - 0.5 * sigma**2) * t + sigma * math.sqrt(t) * rng.standard_normal(int(simulations)))
        if option_type.lower() == "call":
            payoffs = np.maximum(terminal - strike_value, 0.0)
        elif option_type.lower() == "put":
            payoffs = np.maximum(strike_value - terminal, 0.0)
        else:
            raise ValueError("option_type must be call or put")
        discounted = math.exp(-r * t) * payoffs
        result["monte_carlo"] = _finite(discounted.mean())
        result["standard_error"] = _finite(discounted.std(ddof=1) / math.sqrt(len(discounted)))
    return result

from __future__ import annotations

"""A deliberately explicit, close-to-close momentum backtest.

The educational execution convention is important: a moving-average signal is
known at a close, a trade is executed at the *next* close, and the first
return earned by that new position is the return after that execution.  This
avoids treating the close used to make a signal as an executable price.
"""

import math
from typing import Any, Iterable

import numpy as np
import pandas as pd


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _iso_date(value: Any) -> str | None:
    try:
        stamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(stamp):
        return None
    return stamp.date().isoformat()


def _metric_summary(strategy_returns: pd.Series, equity: pd.Series, periods: int) -> dict[str, float | None]:
    returns = pd.to_numeric(strategy_returns, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    final_equity = _finite(equity.iloc[-1]) if len(equity) else None
    total_return = _finite(final_equity - 1.0) if final_equity is not None else None
    if final_equity is None or final_equity < 0:
        annualized_return = None
    elif final_equity == 0:
        annualized_return = -1.0
    else:
        annualized_return = _finite(final_equity ** (252.0 / max(periods, 1)) - 1.0)
    annualized_volatility = _finite(returns.std(ddof=1) * math.sqrt(252.0)) if len(returns) >= 2 else None
    if len(returns) >= 2 and _finite(returns.std(ddof=1)) not in (None, 0.0):
        # Arithmetic excess-return Sharpe, with the contract's rf=0 assumption.
        sharpe = _finite(returns.mean() / returns.std(ddof=1) * math.sqrt(252.0))
    else:
        sharpe = None
    if len(equity):
        drawdown = equity / equity.cummax() - 1.0
        max_drawdown = _finite(drawdown.min())
    else:
        max_drawdown = None
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe,
        "max_drawdown": max_drawdown,
    }


def _empty_result(status: str, parameters: dict[str, Any], warning: str | None = None) -> dict[str, Any]:
    metrics: dict[str, Any] = {
        "total_return": None,
        "annualized_return": None,
        "annualized_volatility": None,
        "sharpe": None,
        "max_drawdown": None,
        "turnover": 0.0,
        "observations": 0,
    }
    result: dict[str, Any] = {
        "status": status,
        "parameters": parameters,
        "metrics": metrics,
        "benchmark": {"total_return": None},
        "equity_curve": [],
        "executions": [],
        "segments": [],
        "ablation": {},
    }
    if warning:
        result["warnings"] = [warning]
    return result


def leakage_check(observations: Iterable[dict[str, Any]], signal_date: str, execution_date: str) -> dict[str, Any]:
    """Check that a signal cannot see data after its signal date.

    ``effective_at`` is the primary visibility timestamp.  ``filed_at`` is
    also checked when present because fundamentals can otherwise leak through
    a market-only backtest.  The signal date itself is allowed; execution must
    be strictly later than the signal date.
    """
    failures: list[str] = []
    try:
        signal = pd.Timestamp(signal_date)
        execution = pd.Timestamp(execution_date)
    except (TypeError, ValueError):
        return {"passed": False, "failures": ["invalid_signal_or_execution_date"]}
    if pd.isna(signal) or pd.isna(execution):
        return {"passed": False, "failures": ["invalid_signal_or_execution_date"]}
    if execution <= signal:
        failures.append("execution_date_must_follow_signal_date")

    for row in observations:
        metric = row.get("metric", "unknown")
        effective_raw = row.get("effective_at")
        if effective_raw is not None:
            try:
                effective = pd.Timestamp(effective_raw)
            except (TypeError, ValueError):
                failures.append(f"invalid_effective_at:{metric}:{effective_raw}")
            else:
                if not pd.isna(effective) and effective > signal:
                    failures.append(f"future_observation:{metric}:{effective.date().isoformat()}")
        filed_raw = row.get("filed_at")
        if filed_raw is not None:
            try:
                filed = pd.Timestamp(filed_raw)
            except (TypeError, ValueError):
                failures.append(f"invalid_filed_at:{metric}:{filed_raw}")
            else:
                if not pd.isna(filed) and filed > signal:
                    failures.append(f"future_filing:{metric}:{filed.date().isoformat()}")
    return {"passed": not failures, "failures": failures}


def _segment_result(name: str, dates: pd.Series, strategy_returns: pd.Series, benchmark_returns: pd.Series) -> dict[str, Any]:
    if len(strategy_returns) == 0:
        return {"name": name, "observations": 0, "total_return": None, "benchmark_total_return": None, "sharpe": None}
    strategy_equity = (1.0 + strategy_returns).cumprod()
    benchmark_equity = (1.0 + benchmark_returns).cumprod()
    summary = _metric_summary(strategy_returns, strategy_equity, max(len(strategy_returns), 1))
    return {
        "name": name,
        "date_start": _iso_date(dates.iloc[0]),
        "date_end": _iso_date(dates.iloc[-1]),
        "observations": int(len(strategy_returns)),
        "total_return": summary["total_return"],
        "benchmark_total_return": _finite(benchmark_equity.iloc[-1] - 1.0),
        "sharpe": summary["sharpe"],
    }


def run_momentum_backtest(
    market: pd.DataFrame,
    transaction_cost: float = 0.001,
    short_window: int = 20,
    long_window: int = 60,
) -> dict[str, Any]:
    """Run a long/flat moving-average strategy with explicit next-close fills."""
    parameters: dict[str, Any] = {
        "transaction_cost": transaction_cost,
        "short_window": short_window,
        "long_window": long_window,
        "risk_free_rate": 0.0,
        "execution": "signal_at_close_then_execute_at_next_close",
        "return_starts": "close_to_close_return_after_execution",
        "starting_equity": 1.0,
    }
    if not isinstance(short_window, (int, np.integer)) or not isinstance(long_window, (int, np.integer)):
        raise TypeError("short_window and long_window must be integers")
    if short_window <= 0 or long_window <= 0 or short_window >= long_window:
        raise ValueError("require 0 < short_window < long_window")
    if not math.isfinite(float(transaction_cost)) or transaction_cost < 0 or transaction_cost >= 1:
        raise ValueError("transaction_cost must be finite and in [0, 1)")
    if market is None or market.empty:
        return _empty_result("insufficient_data", parameters, "No market observations")

    m = market.copy()
    if "date" not in m.columns:
        if "effective_at" in m.columns:
            m["date"] = pd.to_datetime(m["effective_at"], errors="coerce")
        else:
            return _empty_result("invalid", parameters, "Market frame has no date column")
    else:
        m["date"] = pd.to_datetime(m["date"], errors="coerce")
    if "close" not in m.columns:
        if "adj_close" in m.columns:
            m["close"] = m["adj_close"]
        elif "value" in m.columns:
            m["close"] = m["value"]
        else:
            return _empty_result("invalid", parameters, "Market frame has no close column")
    m["close"] = pd.to_numeric(m["close"], errors="coerce")
    m = m.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date", keep="last")
    m = m[m["close"] > 0].reset_index(drop=True)
    if len(m) < long_window + 2:
        return _empty_result("insufficient_data", parameters, f"Need at least {long_window + 2} valid observations")

    m["short_ma"] = m["close"].rolling(short_window, min_periods=short_window).mean()
    m["long_ma"] = m["close"].rolling(long_window, min_periods=long_window).mean()
    valid_signal = m["short_ma"].notna() & m["long_ma"].notna()
    m["signal"] = np.nan
    m.loc[valid_signal, "signal"] = (m.loc[valid_signal, "short_ma"] > m.loc[valid_signal, "long_ma"]).astype(float)
    m["asset_return"] = m["close"].pct_change().fillna(0.0)

    # A signal at i is filled at i+1.  Its new position is deliberately not
    # allowed to earn the return ending at i+1; it starts earning at i+2.
    executed_position = np.full(len(m), np.nan, dtype=float)
    turnover = np.zeros(len(m), dtype=float)
    trade_cost = np.zeros(len(m), dtype=float)
    current_position = 0.0
    executions: list[dict[str, Any]] = []
    for signal_index in range(len(m) - 1):
        signal_value = m.at[signal_index, "signal"]
        if pd.isna(signal_value):
            continue
        execution_index = signal_index + 1
        target_position = float(signal_value)
        changed = abs(target_position - current_position)
        if changed <= 0:
            continue
        execution_date = m.at[execution_index, "date"]
        signal_date = m.at[signal_index, "date"]
        execution_price = float(m.at[execution_index, "close"])
        turnover[execution_index] = changed
        trade_cost[execution_index] = changed * float(transaction_cost)
        executed_position[execution_index] = target_position
        executions.append(
            {
                "signal_date": _iso_date(signal_date),
                "execution_date": _iso_date(execution_date),
                "side": "buy" if target_position > current_position else "sell",
                "target_position": _finite(target_position),
                "turnover": _finite(changed),
                "transaction_cost": _finite(trade_cost[execution_index]),
                "price": _finite(execution_price),
                "model": "next_close",
            }
        )
        current_position = target_position
    m["position"] = pd.Series(executed_position, index=m.index).ffill().fillna(0.0)
    # At date t the position was held from the prior close; a fill at t is
    # charged now and first participates in the return at t+1.
    m["position_for_return"] = m["position"].shift(1).fillna(0.0)
    m["turnover"] = turnover
    m["trade_cost"] = trade_cost
    m["strategy_return"] = m["position_for_return"] * m["asset_return"] - m["trade_cost"]
    m["equity"] = (1.0 + m["strategy_return"]).cumprod()
    m["benchmark"] = (1.0 + m["asset_return"]).cumprod()

    metric_summary = _metric_summary(m["strategy_return"].iloc[1:], m["equity"], max(len(m) - 1, 1))
    metrics = {
        **metric_summary,
        "turnover": _finite(m["turnover"].sum()),
        "observations": int(len(m)),
    }
    benchmark_total = _finite(m["benchmark"].iloc[-1] - 1.0)
    equity_curve = [
        {"date": _iso_date(date), "equity": _finite(equity), "benchmark": _finite(benchmark)}
        for date, equity, benchmark in zip(m["date"], m["equity"], m["benchmark"])
    ]

    # These are measured on the same realized path, not claims about a
    # statistical regime.  The no-cost comparison isolates only fee drag.
    no_cost_returns = m["position_for_return"] * m["asset_return"]
    no_cost_equity = (1.0 + no_cost_returns).cumprod()
    half = max(1, len(m) // 2)
    segments = [
        _segment_result("first_half", m["date"].iloc[1:half], m["strategy_return"].iloc[1:half], m["asset_return"].iloc[1:half]),
        _segment_result("second_half", m["date"].iloc[half:], m["strategy_return"].iloc[half:], m["asset_return"].iloc[half:]),
    ]
    ablation = {
        "name": "transaction_cost_zero",
        "measured": True,
        "transaction_cost": 0.0,
        "total_return_without_cost": _finite(no_cost_equity.iloc[-1] - 1.0),
        "total_return_with_cost": metric_summary["total_return"],
        "fee_drag": _finite(no_cost_equity.iloc[-1] - m["equity"].iloc[-1]),
    }

    return {
        "status": "valid",
        "parameters": parameters,
        "metrics": metrics,
        "benchmark": {"total_return": benchmark_total},
        "equity_curve": equity_curve,
        "executions": executions,
        "segments": segments,
        "ablation": ablation,
        "warnings": ["Educational close-to-close model; no slippage, taxes, or market impact beyond the configured proportional cost."],
    }

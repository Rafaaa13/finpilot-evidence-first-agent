from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .serialization import json_safe


def _number(value: Any, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "not available"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "not available"
    return f"{number:.{digits}f}{suffix}" if number == number else "not available"


def _percent(value: Any) -> str:
    if value is None:
        return "not available"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "not available"
    return f"{number:.2%}" if number == number else "not available"


def build_memo(result: dict[str, Any]) -> str:
    f = result.get("fundamentals", {}) or {}
    m = result.get("market", {}) or {}
    r = result.get("risk", {}) or {}
    s = result.get("score", {}) or {}
    bt = result.get("backtest", {}) or {}
    metrics = bt.get("metrics", {}) or {}
    risk_lab = result.get("risk_lab", {}) or {}
    score = s.get("score")
    score_line = _number(score, 3) if score is not None else "not available because the visible data is insufficient"
    evidence_ids = result.get("evidence_ids", []) or []
    sec_ids = ", ".join(x for x in evidence_ids if str(x).startswith("ev-sec-")) or "none"
    market_ids = ", ".join(x for x in evidence_ids if str(x).startswith("ev-market-")) or "none"
    lines = [
        f"# FinPilot research memo — {result.get('ticker', 'unknown')} as of {result.get('as_of', 'unknown')}",
        "",
        "> This memo is an educational research artifact, not investment advice. Fixture mode uses synthetic data.",
        "",
        "## Decision frame",
        f"The deterministic composite score is **{score_line}** using `{s.get('formula', 'not available')}`. The risk gate is **{r.get('status', 'review')}**.",
        "",
        "## Evidence-linked observations",
        f"- Fundamental: revenue growth {_percent(f.get('revenue_growth_yoy'))}; operating margin {_percent(f.get('operating_margin'))}; FCF margin {_percent(f.get('fcf_margin'))}. [SEC evidence: {sec_ids}]",
        f"- Market: 20-day return {_percent(m.get('return_20d'))}; 60-day return {_percent(m.get('return_60d'))}; 20-day annualized volatility {_percent(m.get('volatility_20d'))}; max drawdown {_percent(m.get('max_drawdown'))}. [Market evidence: {market_ids}]",
        f"- Risk review: {', '.join(r.get('flags', [])) if r.get('flags') else 'no configured risk flag triggered'}.",
        "",
        "## Backtest",
        f"The demo uses {bt.get('parameters', {}).get('execution', 'an explicit lagged execution model')}, with transaction cost {_percent(bt.get('parameters', {}).get('transaction_cost', 0))}.",
        f"- Total return: {_percent(metrics.get('total_return'))}",
        f"- Annualized volatility: {_percent(metrics.get('annualized_volatility'))}",
        f"- Sharpe (simple, risk-free rate assumed zero): {_number(metrics.get('sharpe'))}",
        f"- Maximum drawdown: {_percent(metrics.get('max_drawdown'))}",
        f"- Benchmark total return: {_percent(bt.get('benchmark', {}).get('total_return'))}",
        "",
        "## Credit and fixed-income lab",
    ]
    if risk_lab:
        summary = risk_lab.get("summary", {})
        stress = risk_lab.get("stress", {})
        lines.extend([
            f"- Synthetic credit portfolio: {summary.get('loan_count', 'not available')} loans; baseline expected loss rate {_percent(summary.get('baseline_expected_loss_rate'))}; stressed expected loss rate {_percent(summary.get('stressed_expected_loss_rate'))}.",
            f"- Stress assumptions: PD multiplier {_number(stress.get('pd_multiplier'))}x; LGD shift {_percent(stress.get('lgd_shift'))}.",
            "- Fixed-income and option calculations are available as deterministic tools; they are not regulatory model validation or a pricing opinion.",
        ])
    else:
        lines.append("- Risk lab was not included in this run.")
    lines.extend([
        "",
        "## Limitations",
        "This run is a reproducible fixture demo. A production version needs SEC ticker/CIK mapping, live data caching, restatement policy, provider terms review, broader universes, walk-forward splits and human review before any decision use.",
    ])
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, data: Any) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(json_safe(data), ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )

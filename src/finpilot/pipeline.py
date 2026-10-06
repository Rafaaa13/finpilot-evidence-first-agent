from __future__ import annotations

import datetime as dt
import hashlib
import json
import time
import uuid
import math
from pathlib import Path
from typing import Any

from .agents import run_research_graph, render_claim
from .analytics import composite_score, frames, fundamental_features, market_features, risk_snapshot
from .backtest import leakage_check, run_momentum_backtest
from .data import FixtureProvider, validate_as_of
from .report import build_memo, write_json
from .risk import bond_risk, option_price, run_risk_lab
from .serialization import json_safe


def _next_business_day(as_of: str) -> str:
    day = dt.date.fromisoformat(as_of) + dt.timedelta(days=1)
    while day.weekday() >= 5:
        day += dt.timedelta(days=1)
    return day.isoformat()


def _result_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(json_safe(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _unique_run_id(result_hash: str) -> str:
    return f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:12]}"


def _numeric_consistency(result: dict) -> dict:
    checks = []
    evidence_ids = set(result.get('evidence_ids', []))
    for claim in result.get('claims', []):
        valid = bool(claim.get('evidence_ids')) and set(claim['evidence_ids']).issubset(evidence_ids)
        numbers = claim.get('numeric_values', {})
        for path, value in numbers.items():
            block, field = path.split('.')
            target = result.get(block, {}).get(field)
            valid = valid and target is not None and math.isclose(value, target, rel_tol=1e-10, abs_tol=1e-12)
        try:
            valid = valid and claim['text'] == render_claim(claim['claim_id'], numbers)
        except (ValueError, KeyError):
            valid = False
        checks.append({'claim_id': claim.get('claim_id'), 'passed': bool(valid)})
    return {'passed': all(c['passed'] for c in checks), 'applicable': bool(checks), 'checks': checks,
            'scope': 'IDs + numeric field equality + deterministic template integrity; not semantic LLM accuracy'}


def run_fixture(
    ticker: str = "AAPL",
    as_of: str = "2025-12-31",
    output_dir: str | Path | None = "reports/demo",
    include_risk_lab: bool = True,
    transaction_cost: float = .001, pd_multiplier: float = 1.5, lgd_shift: float = .10,
) -> dict[str, Any]:
    provider = FixtureProvider()
    as_of = validate_as_of(as_of)
    dataset = provider.load(ticker, as_of)
    market_df, fundamental_df = frames(dataset.observations)
    market = market_features(market_df, as_of)
    fundamentals = fundamental_features(fundamental_df, as_of)
    risk = risk_snapshot(market, fundamentals)
    score = composite_score(market, fundamentals, risk)
    backtest = run_momentum_backtest(market_df, transaction_cost=transaction_cost)
    execution_date = _next_business_day(as_of)
    leakage = leakage_check([o.to_dict() for o in dataset.observations], as_of, execution_date)
    risk_lab = run_risk_lab(pd_multiplier=pd_multiplier, lgd_shift=lgd_shift, seed=42) if include_risk_lab else None
    tools = {
        "bond_risk": bond_risk(1000.0, 0.04, 0.045, 5.0, frequency=2, shock_bps=100),
        "option_price": option_price(100.0, 100.0, 0.05, 0.20, 1.0, simulations=2000, seed=42),
    }
    graph = run_research_graph(ticker, as_of, dataset.observations, dataset.evidence, market, fundamentals, risk, score, backtest)
    evidence_ids = [e.evidence_id for e in dataset.evidence]
    result: dict[str, Any] = {
        "ticker": "DEMO",
        "requested_ticker": ticker.upper(),
        "as_of": as_of,
        "mode": "fixture",
        "data_manifest": {
            "source": dataset.source_name,
            "metadata": dataset.metadata,
            "observation_count": len(dataset.observations),
            "evidence_count": len(dataset.evidence),
        },
        "market": market,
        "fundamentals": fundamentals,
        "risk": risk,
        "score": score,
        "backtest": backtest,
        "leakage_check": leakage,
        "risk_lab": risk_lab,
        "risk_tools": tools,
        "evidence_ids": evidence_ids,
        "claims": graph["claims"],
        "skeptic_flags": graph["skeptic_flags"],
        "trace": graph["trace"],
        "evidence_ledger": graph["evidence_ledger"],
    }
    result["evaluation"] = {
        "citation_coverage": 1.0 if result["claims"] and all(c.get("evidence_ids") for c in result["claims"]) else 0.0,
        "numeric_consistency": _numeric_consistency(result),
        "point_in_time_gate": leakage["passed"],
        "reproducible_seed": dataset.metadata["seed"],
    }
    result_hash = _result_hash(result)
    result["result_hash"] = result_hash
    result["run_id"] = _unique_run_id(result_hash)
    if output_dir is not None:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        write_json(out / f"run_{result['run_id']}.json", result)
        (out / f"research_memo_{result['run_id']}.md").write_text(build_memo(result), encoding="utf-8")
    return result

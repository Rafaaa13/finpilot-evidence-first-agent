from __future__ import annotations

"""Deterministic evidence assembly; the optional model agent lives in runtime.py."""
from typing import Any
from .domain import Evidence, Observation


def render_claim(claim_id: str, values: dict) -> str:
    if claim_id == 'claim-revenue-growth':
        return f"最新可见年度收入同比 {values['fundamentals.revenue_growth_yoy']:.2%}。数据为合成财报，不是真实公司披露。"
    if claim_id == 'claim-momentum':
        return f"近20日价格收益 {values['market.return_20d']:.2%}，近20日年化波动 {values['market.volatility_20d']:.2%}。合成路径不代表投资表现。"
    raise ValueError('unknown claim template')


def run_research_graph(ticker: str, as_of: str, observations: list[Observation], evidence: list[Evidence], market: dict, fundamentals: dict, risk: dict, score: dict, backtest: dict) -> dict:
    claims, trace = [], []
    sec = tuple(e.evidence_id for e in evidence if e.source == 'fixture-sec')[-2:]
    price = tuple(e.evidence_id for e in evidence if e.source == 'fixture-market')
    trace.append({'node': 'resolver', 'status': 'completed', 'detail': f'DEMO synthetic corpus; cutoff {as_of}; input label {ticker}'})
    trace.append({'node': 'data_steward', 'status': 'completed' if observations else 'abstained', 'detail': f'{len(observations)} visible observations; filing-date gate; no live data'})
    if fundamentals.get('revenue_growth_yoy') is not None and len(sec) >= 2:
        values = {'fundamentals.revenue_growth_yoy': fundamentals['revenue_growth_yoy']}
        claims.append({'claim_id': 'claim-revenue-growth', 'text': render_claim('claim-revenue-growth', values), 'claim_type': 'fundamental', 'numeric_values': values, 'evidence_ids': list(sec), 'formula_refs': fundamentals['formula_refs']})
    if market.get('return_20d') is not None and market.get('volatility_20d') is not None and price:
        values = {'market.return_20d': market['return_20d'], 'market.volatility_20d': market['volatility_20d']}
        claims.append({'claim_id': 'claim-momentum', 'text': render_claim('claim-momentum', values), 'claim_type': 'market', 'numeric_values': values, 'evidence_ids': list(price), 'formula_refs': market['formula_refs']})
    for node, status, detail in [('fundamental_analyst', fundamentals.get('status'), 'deterministic filing ratios'), ('market_analyst', market.get('status'), 'deterministic trailing-window metrics'), ('risk_officer', risk.get('status'), ', '.join(risk.get('flags', [])) or 'no threshold triggered')]:
        trace.append({'node': node, 'status': status, 'detail': detail})
    flags = list(risk.get('flags', []))
    if not claims:
        flags.append('insufficient_evidence_abstain')
    trace.append({'node': 'skeptic', 'status': 'review' if flags else 'completed', 'detail': '; '.join(flags) or 'IDs and numeric templates checked; semantic model quality not measured'})
    trace.append({'node': 'writer', 'status': 'completed' if claims else 'abstained', 'detail': f'{len(claims)} template claims. Rules, not LLM calls.'})
    return {'status': 'review' if flags else 'pass', 'claims': claims, 'skeptic_flags': flags, 'trace': trace, 'evidence_ledger': [e.to_dict() for e in evidence], 'score': score, 'backtest': backtest}

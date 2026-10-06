from __future__ import annotations
import argparse
import json
from .pipeline import run_fixture
from .risk import run_risk_lab
from .report import write_json
from .serialization import json_safe


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog='finpilot')
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('demo', help='offline synthetic research')
    d.add_argument('--mode', choices=['fixture'], default='fixture')
    d.add_argument('--ticker', default='DEMO'); d.add_argument('--as-of', default='2025-12-31')
    d.add_argument('--output', default='reports/demo'); d.add_argument('--no-risk-lab', action='store_true')
    r = sub.add_parser('risk'); r.add_argument('--pd-multiplier', type=float, default=1.5)
    r.add_argument('--lgd-shift', type=float, default=.1); r.add_argument('--seed', type=int, default=42)
    r.add_argument('--output', default='reports/evaluation/risk_lab.json')
    e = sub.add_parser('eval'); e.add_argument('--output', default='reports/evaluation/eval.json')
    s = sub.add_parser('serve'); s.add_argument('--host', default='127.0.0.1'); s.add_argument('--port', type=int, default=8765)
    a = sub.add_parser('agent'); a.add_argument('--question', required=True); a.add_argument('--live-model', action='store_true'); a.add_argument('--output', default=None)
    w = sub.add_parser('export'); w.add_argument('--output', default='FinPilot演示工作台.html')
    args = p.parse_args(argv)
    if args.command == 'export':
        from .ui import build_workbench
        from pathlib import Path
        path=Path(args.output); path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(build_workbench(), encoding='utf-8')
        print(str(path)); return
    if args.command == 'serve':
        from .server import serve
        serve(args.host, args.port); return
    if args.command == 'demo':
        r = run_fixture(args.ticker, args.as_of, args.output, include_risk_lab=not args.no_risk_lab)
        out = {k:r[k] for k in ['run_id','result_hash','risk','leakage_check']}
    elif args.command == 'risk':
        out = run_risk_lab(args.pd_multiplier, args.lgd_shift, args.seed); write_json(args.output, out)
        out = out['summary']
    elif args.command == 'eval':
        from .evaluation import evaluate
        out = evaluate(); write_json(args.output, out)
    elif args.command == 'agent':
        from .runtime import run_agent
        from .integrations import LlmClient
        client = LlmClient.from_env() if args.live_model else None
        if args.live_model and client is None:
            p.error('--live-model requires FINPILOT_LLM_ENDPOINT; no secret in command arguments')
        out = run_agent(run_fixture('DEMO', output_dir=None), args.question, client)
        if args.output: write_json(args.output, out)
    print(json.dumps(json_safe(out), ensure_ascii=False, indent=2, allow_nan=False))
    if args.command == 'eval' and out['status'] != 'pass':
        raise SystemExit(1)

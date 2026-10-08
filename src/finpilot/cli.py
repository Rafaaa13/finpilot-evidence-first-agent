from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_fixture
from .risk import run_risk_lab
from .report import write_json
from .serialization import json_safe


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="finpilot", description="Local-first financial research cockpit")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run single-entity synthetic research")
    demo.add_argument("--ticker", default="DEMO"); demo.add_argument("--as-of", default="2025-12-31")
    demo.add_argument("--output", default="reports/demo"); demo.add_argument("--no-risk-lab", action="store_true")
    research = sub.add_parser("research", help="run local CSV research or the offline synthetic workflow")
    research.add_argument("--as-of", default="2025-12-31")
    research.add_argument("--method", choices=["equal", "score_weighted", "vol_inverse"], default="equal")
    research.add_argument("--weight-cap", type=float, default=.30)
    research.add_argument("--output", default="reports/research")
    research.add_argument("--stocks", default=None, help="authorized local stocks.csv; absent means synthetic demo")
    research.add_argument("--prices", default=None, help="authorized local prices.csv; requires --stocks")
    risk = sub.add_parser("risk", help="run the synthetic credit/fixed-income risk lab")
    risk.add_argument("--pd-multiplier", type=float, default=1.5); risk.add_argument("--lgd-shift", type=float, default=.1)
    risk.add_argument("--seed", type=int, default=42); risk.add_argument("--output", default="reports/evaluation/risk_lab.json")
    evaluation = sub.add_parser("eval", help="run deterministic offline acceptance cases")
    evaluation.add_argument("--output", default="reports/evaluation/eval.json")
    agent = sub.add_parser("agent", help="run bounded tool-selection agent")
    agent.add_argument("--question", required=True); agent.add_argument("--live-model", action="store_true"); agent.add_argument("--output", default=None)
    export = sub.add_parser("export", help="export a standalone HTML workbench")
    export.add_argument("--output", default="FinPilot演示工作台.html")
    serve = sub.add_parser("serve", help="serve the local workbench on loopback")
    serve.add_argument("--host", default="127.0.0.1"); serve.add_argument("--port", type=int, default=8765)
    cases = sub.add_parser("cases", help="inspect public historical reference snapshots without downloading")
    cases.add_argument("--case-id", default=None)
    cases.add_argument("--output", default=None)
    data = sub.add_parser("data", help="inspect data sources without contacting them by default")
    data_sub = data.add_subparsers(dest="data_command", required=True)
    doctor = data_sub.add_parser("doctor", help="run offline dependency and local snapshot checks")
    doctor.add_argument("--provider", choices=["user_snapshot", "yfinance", "sec_edgar"], default=None)
    doctor.add_argument("--stocks", default=None, help="authorized local stocks.csv to validate")
    doctor.add_argument("--prices", default=None, help="authorized local prices.csv to validate")
    doctor.add_argument("--as-of", default=None, help="optional YYYY-MM-DD cutoff for a local snapshot")
    fetch = sub.add_parser("fetch", help="explicitly fetch provider data; never falls back to synthetic data")
    fetch.add_argument("--provider", choices=["yfinance", "sec_edgar"], required=True)
    fetch.add_argument("--ticker", required=True)
    fetch.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    fetch.add_argument("--end", required=True, help="YYYY-MM-DD inclusive")
    fetch.add_argument("--cik", default=None, help="explicit SEC CIK; ticker-to-CIK guessing is disabled")
    fetch.add_argument("--user-agent", default=None, help="SEC contact user-agent; do not put secrets here")
    fetch.add_argument("--allow-network", action="store_true", help="explicitly authorize a network request")
    fetch.add_argument("--accept-terms", action="store_true", help="confirm provider terms were reviewed")
    fetch.add_argument("--output", default=None, help="write normalized unverified JSON manifest")
    fetch.add_argument("--prices-output", default=None, help="also write legacy prices.csv (yfinance only); retain JSON provenance")
    args = parser.parse_args(argv)
    if args.command == "export":
        from .ui import build_workbench
        path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(build_workbench(), encoding="utf-8")
        print(path); return
    if args.command == "serve":
        from .server import serve
        serve(args.host, args.port); return
    if args.command == "cases":
        from .cases import analyze_all_reference_cases, historical_case_catalog, financial_casebook, all_financial_cases
        if args.case_id:
            catalog = historical_case_catalog()
            matches = [case for case in catalog["cases"] if case.get("case_id") == args.case_id]
            if not matches:
                parser.error(f"unknown case_id: {args.case_id}")
            output = {"catalog": catalog, "analysis": [__import__("finpilot.cases", fromlist=["analyze_reference_case"]).analyze_reference_case(matches[0])]}
        else:
            output = {"catalog": historical_case_catalog(), "analysis": analyze_all_reference_cases(), "financial_casebook": financial_casebook(), "financial_analysis": all_financial_cases()}
        if args.output: write_json(args.output, output)
        print(json.dumps(json_safe(output), ensure_ascii=False, indent=2, allow_nan=False)); return
    if args.command == "data":
        from .data_sources import ProviderError, data_doctor
        try:
            output = data_doctor(
                provider=args.provider,
                stocks_path=args.stocks,
                prices_path=args.prices,
                as_of=args.as_of,
            )
        except (OSError, ProviderError) as exc:
            parser.error(str(exc))
        print(json.dumps(json_safe(output), ensure_ascii=False, indent=2, allow_nan=False))
        return
    if args.command == "fetch":
        from .data_sources import (
            ProviderError,
            SecEdgarProvider,
            SourcePolicy,
            YFinanceProvider,
        )
        if args.prices_output and (args.provider != "yfinance" or not args.output):
            parser.error("--prices-output requires --provider yfinance and --output to retain provenance")
        if args.prices_output and Path(args.prices_output).resolve() == Path(args.output).resolve():
            parser.error("JSON and prices CSV output paths must differ")
        try:
            policy = SourcePolicy(
                allow_network=args.allow_network,
                accept_terms=args.accept_terms,
                user_agent=args.user_agent,
            )
            if args.provider == "yfinance":
                result = YFinanceProvider(policy=policy).fetch(args.ticker, args.start, args.end)
            else:
                result = SecEdgarProvider(policy=policy, cik=args.cik).fetch(
                    args.ticker, args.start, args.end
                )
            output = result.to_dict()
        except (OSError, ProviderError) as exc:
            parser.error(str(exc))
        if args.output:
            write_json(args.output, output)
        if args.prices_output:
            path = Path(args.prices_output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(result.prices_csv(), encoding="utf-8")
        print(json.dumps(json_safe(output), ensure_ascii=False, indent=2, allow_nan=False))
        return
    if args.command == "demo":
        result = run_fixture(args.ticker, args.as_of, args.output, include_risk_lab=not args.no_risk_lab)
        output = {key: result[key] for key in ("run_id", "result_hash", "risk", "leakage_check")}
    elif args.command == "research":
        from .investment import analyze_investment, demo_inputs
        if args.prices and not args.stocks:
            parser.error("research --prices requires --stocks")
        if args.stocks:
            from .data_sources import UserSnapshotProvider, ProviderError, _read_local_csv
            try:
                stocks_text = _read_local_csv(args.stocks)
                prices_text = _read_local_csv(args.prices) if args.prices else ""
                snapshot = UserSnapshotProvider().load(stocks_text, prices_text, args.as_of)
                result = analyze_investment(
                    stocks_text, prices_text, args.as_of, method=args.method,
                    weight_cap=args.weight_cap, data_kind="user_import",
                )
                manifest = snapshot.to_dict()
                manifest.pop("records")  # Keep provenance, not a duplicate of the raw CSV.
            except (OSError, ProviderError, ValueError) as exc:
                parser.error(str(exc))
        else:
            inputs = demo_inputs()
            inputs["as_of"] = args.as_of
            result = analyze_investment(**inputs, method=args.method, weight_cap=args.weight_cap)
        output = {key: result[key] for key in ("schema_version", "data_kind", "as_of", "screen", "portfolio", "risk", "content_hash")}
        if args.stocks:
            output["provider_manifest"] = manifest
            # New local-CSV path persists the existing deterministic research
            # result and its separate input manifest; old synthetic CLI is unchanged.
            write_json(Path(args.output) / "research.json", result)
            write_json(Path(args.output) / "input-manifest.json", manifest)
    elif args.command == "risk":
        result = run_risk_lab(args.pd_multiplier, args.lgd_shift, args.seed); write_json(args.output, result); output = result["summary"]
    elif args.command == "eval":
        from .evaluation import evaluate
        output = evaluate(); write_json(args.output, output)
    else:
        from .runtime import run_agent
        from .integrations import LlmClient
        client = LlmClient.from_env() if args.live_model else None
        if args.live_model and client is None:
            parser.error("--live-model requires FINPILOT_LLM_ENDPOINT; do not put secrets in command arguments")
        output = run_agent(run_fixture("DEMO", output_dir=None), args.question, client)
        if args.output: write_json(args.output, output)
    print(json.dumps(json_safe(output), ensure_ascii=False, indent=2, allow_nan=False))
    if args.command == "eval" and output["status"] != "pass": raise SystemExit(1)

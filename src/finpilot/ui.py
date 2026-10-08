from __future__ import annotations

import json
from pathlib import Path

from .evaluation import evaluate
from .investment import analyze_investment, demo_inputs
from .cases import historical_case_catalog, analyze_all_reference_cases, financial_casebook, all_financial_cases
from .pipeline import run_fixture
from .construction import construct
from .macro import load_public_macro
from .market_cases import load_sp500_snapshot, market_case_windows
from .serialization import json_safe


def build_workbench(server: bool = False) -> str:
    demo=demo_inputs()
    periods=['2025-12-31','2022-12-31','2020-12-31']
    investment_cases={}
    for period in periods:
        case_inputs=demo_inputs(period)
        investment_cases[period]={
            'balanced': analyze_investment(**case_inputs, method='equal', profile='balanced', weight_cap=.30),
            'quality': analyze_investment(**case_inputs, method='vol_inverse', profile='quality', weight_cap=.20),
            'value': analyze_investment(**case_inputs, method='score_weighted', profile='value', weight_cap=.30),
        }
    investment=investment_cases['2025-12-31']
    legacy_investment={'equal':investment['balanced'],'score_weighted':investment['value'],'vol_inverse':investment['quality'],'templates':investment}
    construction_cases={
        'balanced': construct(investment['balanced'],demo['prices_csv'],method='equal',cash_floor=.10,asset_cap=.30,sector_cap=.50,capital=100000),
        'quality': construct(investment['quality'],demo['prices_csv'],method='vol_inverse',cash_floor=.20,asset_cap=.20,sector_cap=.40,capital=100000),
        'value': construct(investment['value'],demo['prices_csv'],method='score_weighted',cash_floor=.10,asset_cap=.30,sector_cap=.50,capital=100000),
    }
    construction=construction_cases['balanced']
    payload = {
        "server": server,
        "construction": construction,
        "construction_cases": construction_cases,
        "runs": {d: run_fixture("DEMO", d, output_dir=None) for d in ["2025-12-31", "2023-12-31", "2021-06-30"]},
        "investment": legacy_investment,
        "investment_cases": investment_cases,
        "investment_inputs": {"stocks_csv": demo["stocks_csv"], "prices_csv": demo["prices_csv"], "as_of": demo["as_of"], "data_kind": demo["data_kind"]},
        "evaluation": evaluate(),
        "historical_cases": {"catalog": historical_case_catalog(), "analysis": analyze_all_reference_cases()},
        "financial_cases": {"catalog": financial_casebook(), "analysis": all_financial_cases()},
        "macro": load_public_macro(),
        "sp500_snapshot": load_sp500_snapshot(),
        "market_cases": market_case_windows(),
    }
    raw = json.dumps(json_safe(payload), ensure_ascii=False, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = Path(__file__).with_name("workbench.html").read_text(encoding="utf-8")
    marker = '<script id="payload" type="application/json">__PAYLOAD__</script>'
    return template.replace(marker, '<script id="payload" type="application/json">' + raw + "</script>")


def render_html(result: dict) -> str:
    return build_workbench()


if __name__ == "__main__":
    print(build_workbench())

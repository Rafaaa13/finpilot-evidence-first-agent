# FinPilot

> Screen a research universe, build a capped long-only portfolio, stress it on common-date returns, and export an evidence-linked memo — locally, reproducibly, without an LLM.

FinPilot is a local-first financial research and risk workbench. Its primary user flow is investment research: validate a cutoff date and user-provided snapshot, screen candidates under explicit financial rules, build a transparent portfolio with a hard position cap and cash, run common-date stress diagnostics, and export a memo with evidence and assumptions. Credit risk, fixed-income, and option tools support risk/model-validation, data-governance, ALM/fixed-income, fintech, and AI-product interview tracks.

The bundled demo uses synthetic `DEMO01`–`DEMO08` entities. They are not real securities, and no result is investment advice or evidence of future returns.

## Five-minute quick start

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m finpilot research --as-of 2025-12-31 --method equal
python -m finpilot export --output FinPilot-workbench.html
python -m finpilot serve
```

Open `http://127.0.0.1:8765`. The Investment Research page walks through: screening, exclusion reasons, portfolio weights/cash, three stress scenarios, evidence, and export. The workbench also has Credit Risk, Fixed Income & Options, Evaluation, and Interview Training pages.

## Local data import

`stocks.csv` must have exactly:

```text
symbol,name,sector,currency,price_as_of,price,eps_ttm,revenue_growth,operating_margin,fcf_margin,debt_to_equity,period_end,filed_at,source
```

`prices.csv` must have exactly:

```text
date,symbol,adj_close
```

Ratios are decimal values, prices must be positive, and a file must use one currency. Future filings/prices, stale snapshots, duplicate rows, invalid units, malformed dates, and missing metrics fail closed or become explicit exclusions. An imported file is labelled “user provided, not independently verified”; the `source` field is provenance, not proof of authenticity.

Synthetic examples are in [`examples/`](examples/). The import contract is documented in [`docs/data-contract.md`](docs/data-contract.md).

Three real-data workflows are available without changing the offline default: authorized local CSV (`data doctor` then `research --stocks ... --prices ...`), explicit opt-in provider fetch (lazy yfinance or raw SEC companyfacts), and versioned case templates in [`examples/real_cases/`](examples/real_cases/). Fetch requires both `--allow-network` and `--accept-terms`, never silently falls back to fixtures, and returns `real_user_fetch` / `verified=false`. Missing dependencies are reported rather than installed.

The repository also includes a small public historical reference snapshot and an official-public financial casebook for Apple FY2024, Microsoft FY2024, NVIDIA FY2024, and WTI April 2020. These are citation-bearing case facts and questions, not complete company datasets, real-time data, or investment recommendations.

## Why the LLM is optional

The deterministic core completes validation, financial screening, portfolio construction, cash preservation, common-date stress, evidence, and memo generation without an API key. An optional OpenAI-compatible endpoint can help understand a question, select existing findings, create diligence questions, and improve wording. It cannot calculate or change PE, returns, expected loss, weights, point-in-time gates, or evidence IDs. The workbench previews the summary before sending it; raw CSV files and keys are not sent by default.

```bash
export FINPILOT_LLM_ENDPOINT=http://127.0.0.1:11434/v1
export FINPILOT_LLM_MODEL=your-local-model
export FINPILOT_LLM_API_KEY=
python -m finpilot agent --live-model --question "Explain exclusion reasons and diligence questions"
```

## Architecture

```text
CSV / synthetic fixture
        ↓
field, currency, date, filing and provenance checks
        ↓
financial screen: PE / growth / margins / leverage / completeness
        ↓
portfolio: equal / score / inverse-vol + hard cap + cash
        ↓
common-date risk: parametric / historical / correlation stress
        ↓
evidence ledger + JSON + research memo
        ↑
optional LLM: question understanding and bounded explanation only
```

Python modules include `investment.py` for the user-facing CSV workflow, `portfolio.py` for long-only weights and common-date stress, `data.py`/`analytics.py` for observations and point-in-time calculations, `risk.py` for credit/fixed-income/options, `integrations.py` for opt-in MCP/LLM transport, and `advisor.py` for previewed LLM enhancement.

## Interview framing

For AI product roles, present FinPilot as a product decision: a narrow research task, explicit states, deterministic tools, evidence UX, LLM boundaries, failure handling, privacy, and evaluation. For finance roles, explain EAD-weighted EL, the difference between reporting period and filing date, PE/quality/growth rules, hard position caps, common-date covariance, duration/convexity/DV01, and why synthetic metrics do not prove calibration.

Use STAR: the situation was that research tools mix retrieval, arithmetic, portfolio rules, and narrative; the task was to build a local reproducible workflow; the actions were data contracts, fail-closed screening, transparent allocation, dated stress, evidence, and bounded LLM routing; the result is a runnable local workflow with tests and explicit limitations. Do not claim live securities, alpha, external users, production deployment, IFRS 9 validation, or model benchmark results.

## Status and limitations

Implemented and locally tested: synthetic investment research, CSV validation, portfolio cap/cash, common-date stress, credit stress, fixed-income/options calculations, bounded MCP/LLM schemas, evidence, localhost server, and standalone workbench. The test suite is an offline engineering check, not a user study or model benchmark. Optional yfinance/SEC adapters are covered by injected offline mocks, not live integration tests. Accounting restatements, corporate actions, liquidity, transaction-cost backtesting, external users, source licensing, and commercial deployment require separate work.

See [`docs/product-v03.md`](docs/product-v03.md), [`docs/data-contract.md`](docs/data-contract.md), [`docs/architecture.md`](docs/architecture.md), [`docs/interview-playbook.md`](docs/interview-playbook.md), [`docs/interview-v03.md`](docs/interview-v03.md), [`docs/capability-map.md`](docs/capability-map.md), [`docs/resume.md`](docs/resume.md), [`docs/integrations.md`](docs/integrations.md), [`docs/advisor.md`](docs/advisor.md), and [`docs/model-card.md`](docs/model-card.md).

## Safety

Do not commit API keys, personal resumes, private interview material, client data, or restricted provider downloads. The prototype binds to loopback, defaults to offline data, uses read-only allowlists, and does not grant an LLM shell, SQL, or arbitrary network access.

## Public references

[SEC EDGAR API documentation](https://www.sec.gov/edgar/sec-api-documentation) · [MCP specification](https://modelcontextprotocol.io/specification/latest) · [TradingAgents](https://github.com/TauricResearch/TradingAgents) · [OpenBB](https://github.com/OpenBB-finance/OpenBB) · [Qlib](https://github.com/microsoft/qlib)

MIT License. Data-provider, model-provider, and financial-decision responsibilities remain separate from the repository license.

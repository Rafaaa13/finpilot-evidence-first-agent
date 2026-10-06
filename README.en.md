# FinPilot

FinPilot is an evidence-first workspace for financial risk and research. It keeps point-in-time visibility, formulas, citations, risk gates, and reproducible run records in one workflow. The goal is not to replace an analyst or risk professional with a trading answer. The goal is to make every reviewable statement answer four questions: when was the data visible, how was it calculated, what supports it, and where should the workflow stop for human review?

The default path is offline and deterministic. Prices, filing-like fields, and loan samples in the fixture are synthetic. Passing `AAPL` or `MSFT` to the CLI does not turn the fixture into real security data. The repository does not enable network access by default, does not read secrets by default, and did not connect a local SEC or Yahoo MCP in this session. The current baseline includes point-in-time data, market/fundamental analysis, lagged backtesting, credit stress, model-validation readouts, fixed-income/option tools, strict JSON, an evidence ledger, a bounded Agent path, offline evaluation, a localhost-only server, and an exportable workbench. Live providers and live models remain explicit opt-in integrations.

This is not investment advice, a production risk approval system, an execution system, or a regulatory model. Numeric examples are educational assumptions. No return, risk, latency, cost, accuracy, or user metric should be presented as measured unless it comes from an actual run log or report. Commercial deployment and training have not been completed, and the project makes no promise about GitHub stars, hiring outcomes, or coverage of every job description.

## Why FinPilot exists

Financial research tools often mix retrieval, numerical computation, and narrative generation. That makes it difficult to tell whether a number is an observation, a derived value, or a language-model statement. Filing dates and reporting periods can be confused, and a backtest can accidentally trade on the same bar that created its signal. FinPilot takes the opposite approach: deterministic rules run first, an optional language model handles bounded explanation work second, and unverifiable facts, units, dates, or tool outputs fail closed instead of being guessed.

The project supports two job-search tracks. The AI product track requires concrete evidence for interviews, PRDs, event SQL, frozen evaluations, RAG/agent tools, cost, security, and cross-functional delivery. The finance track is deliberately not described as a confirmed list of quant-investment roles. The verified role families are risk management and model validation; financial infrastructure and data governance; ALM, fixed income, and financial markets; and fintech and risk products. FinPilot materials map transferable capabilities to those families and state which claims still require personal hand calculation, parameter changes, and review of failure cases.

## Quick start

Python 3.10 or newer is required. Runtime dependencies are the `numpy` and `pandas` declared by the project; tests use the standard-library `unittest`. From the repository root:

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
python -m finpilot demo --ticker AAPL --as-of 2025-12-31 --output reports/demo
python -m finpilot eval --output /tmp/finpilot-eval.json
python -m finpilot export --output /tmp/FinPilot-workbench.html
python -m finpilot agent --question 'credit stress loss and duration risk'
```

The demo writes a JSON run record and a Markdown research memo. The review entry points are `source`, `raw_ref`, `effective_at`, `filed_at`, `formula_refs`, `evidence_ids`, and `trace`. They describe synthetic fixture data, not real AAPL market or financial data.

The current CLI commands are real, offline-tested paths. `eval` is a deterministic acceptance suite, not a model benchmark; `serve` binds to `127.0.0.1` and uses synthetic fixture data; `agent` uses a transparent offline router by default. Passing `--live-model` is explicit opt-in and requires a configured endpoint. No SEC/Yahoo MCP has been installed or connected in this delivery.

## Workflow

A run should first fix the ticker, `as_of`, mode, and data manifest. The data layer preserves the observation period, filing time, effective time, unit, source locator, and raw reference. The analytics layer reads only facts visible by the cutoff. Deterministic rules compute market features, fundamental features, a risk snapshot, and a descriptive composite score. The backtest uses an explicit lagged execution model and reports transaction costs, a benchmark, and a leakage check. The evidence layer binds narrative claims to evidence IDs. Only then may a report be rendered or an optional LLM perform constrained wording work.

`fail-closed` is the default. Unknown units, unparseable dates, incompatible tool output, missing evidence, unvalidated model output, or an execution date no later than the signal date should produce `review`, `blocked`, or `insufficient_data`; they should not trigger imputation, guessed field meanings, or false precision.

## Capability and status

| Capability | Public wording now | Do not claim |
| --- | --- | --- |
| Offline fixture, evidence fields, market/fundamental features | Baseline code path and readable contracts | Real securities, real filings, or user validation |
| Momentum backtest | Educational next-observation execution baseline | Predictive alpha, tradable returns, or investment advice |
| Credit stress, loan loss, bond sensitivity | Implemented deterministic tools, integrated in the fixture pipeline and covered by independent hand-check tests | IFRS 9, regulatory capital, real calibration, or approval conclusions |
| RAG/agent and MCP | Bounded offline tool-selection path, optional two-call model route, and read-only MCP transport; no live SEC/Yahoo provider connected | Installed MCPs, live data access, or production integration |
| LLM | Optional structured explanation path separated from deterministic outputs | Letting an LLM perform arithmetic, point-in-time checks, or safety decisions |
| User research and product metrics | Interview protocol, event dictionary, and SQL drafts | External interviews, retention, accuracy, or time-saved metrics already achieved |

TradingAgents, OpenBB, and Qlib are public design references, not FinPilot runtime dependencies. FinPilot does not copy their code. Protocol capabilities should be implemented only when needed, and “referenced” must not be written as “installed” or “connected.”

## Interview framing

Frame the project as an evidence-first financial AI product-engineering problem, not as a stock-picking robot. A 90-second answer should establish the problem, constraints, deterministic core, and validation boundary. A five-minute answer can then explain point-in-time visibility, unit discipline, backtest lag, fail-closed behavior, cost, and security. Every number must come from a real run or experiment log. If AI assisted development, the basic resume version should say so accurately and state that the candidate personally checked arithmetic, changed parameters, and reviewed failure cases. Planned risk experiments, interviews, team leadership, or live model results must not appear as completed experience before personal acceptance.

See [`docs/interview-playbook.md`](docs/interview-playbook.md) for detailed answers, finance examples, a fourteen-day practice plan, and daily evidence templates. See [`docs/capability-map.md`](docs/capability-map.md) for the role-family mapping.

## Security and privacy

Do not commit real model keys, original personal resumes, private financial-agent documents, client data, or unpublished interview notes. An external model path may receive only approved synthetic or public summaries; it must not receive keys, browser credentials, or unapproved raw documents. Tool access must be read-only and bounded by allowlists, call limits, response limits, and token limits. An LLM must not receive arbitrary shell, SQL, or network execution authority.

Do not paste secrets, personal information, or client material into a public issue. Use the issue templates for ordinary bugs and feature requests, and use a private maintainer channel for sensitive reports.

## Reference entry points

The links below are official entry points for independently checking protocols or public project designs. They are not dependency declarations and do not guarantee data terms, licenses, or performance.

SEC EDGAR API documentation: <https://www.sec.gov/edgar/sec-api-documentation>.

Model Context Protocol specification: <https://modelcontextprotocol.io/specification/latest>.

TradingAgents public repository: <https://github.com/TauricResearch/TradingAgents>.

OpenBB public repository: <https://github.com/OpenBB-finance/OpenBB>.

Qlib public repository: <https://github.com/microsoft/qlib>.

## License

This project uses the MIT License; see [`LICENSE`](LICENSE). The license does not override data-provider terms, model-service terms, or the user's responsibility for financial decisions.

For architecture, release, and model-boundary details, see [`docs/architecture.md`](docs/architecture.md), [`docs/publish.md`](docs/publish.md), and [`docs/model-card.md`](docs/model-card.md).

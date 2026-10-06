# FinPilot architecture

## System boundary

FinPilot is an offline-first Python application. The public path is a deterministic fixture pipeline. A future live path may add read-only SEC and market-data adapters and an optional OpenAI-compatible model adapter. The live path is intentionally not assumed to be installed or connected.

```text
CLI / local server
        |
application pipeline
        |
+-------+----------+-------------------+
| data  | analytics | risk / backtest  |
|       |           |                   |
+-------+----------+-------------------+
        |
 evidence ledger + point-in-time gate
        |
 deterministic report + optional bounded explanation
```

## Data contract

An `Observation` contains entity, metric, value, unit, period, filed/effective dates, source locator, raw reference and quality status. A `raw_ref` is a SHA-256 reference to the canonical observation record in fixture mode. The fixture uses an internal `DEMO` identity even when the CLI input is AAPL or MSFT. This prevents synthetic values being mistaken for a real security.

Fundamental observations are visible only when `filed_at <= as_of`; market observations are visible only when `effective_at <= as_of`. This is a deliberately small point-in-time policy. A production provider needs to handle amended filings, restatements, timezone/cutoff convention and provider-specific revisions explicitly.

## Deterministic computation

The analytics layer calculates returns, volatility, drawdown, fundamental margins, a descriptive composite score and review flags. The score is a heuristic demonstration, not a forecast. Credit risk calculates expected loss as an EAD-weighted quantity and caps stressed PD/LGD. The risk lab uses a fixed chronological synthetic split and reports AUC, Brier and ECE as plumbing checks, not regulatory validation. Bond tools report price, Macaulay/modified duration, convexity, DV01 and a parallel-rate scenario. The option tool reports Black–Scholes and an optional seeded Monte Carlo check.

The backtest has an explicit convention: the signal is known at a close, a trade is filled at the next close, and the new position starts earning the following close-to-close return. Transaction cost is charged at the fill. It reports a benchmark, segments and a same-path zero-cost fee-drag ablation. It does not model spread, slippage, taxes, market impact, corporate actions or portfolio-level liquidity.

## Agent boundary

The current `agents.py` is a deterministic trace-producing orchestrator. Its node names model a product state machine: resolver, data steward, fundamental analyst, market analyst, risk officer, research manager, skeptic and writer. This is an auditable product abstraction, not evidence that a live LLM was called.

If a model adapter is added, the model receives an allowlisted context and may return bounded claims that cite existing evidence IDs. The application must reject unknown evidence IDs, non-JSON output, numeric overrides, arbitrary tool names, shell/SQL requests, excessive claims and missing caveats. Numeric calculations, point-in-time checks and risk decisions remain outside the model.

## Failure policy

The application uses `review`, `blocked` and `insufficient_data` as first-class states. Unknown units, invalid dates, future observations, absent evidence, insufficient windows and model-schema failures do not become zeroes. Serialization converts non-finite values to JSON null. Reports include limitations and source kind so that synthetic fixture evidence cannot look like a public filing.

## Reproducibility

A run has a content-derived `result_hash` and a separate timestamped `run_id`. The hash lets a reviewer compare two runs; the run ID prevents one run from overwriting another. A production version should also persist dependency lock information, provider version, request parameters and a data snapshot manifest.

## Why not fork a large framework

TradingAgents, OpenBB and Qlib are useful public design references, but they are not runtime dependencies. A small project makes the separation between data, calculations, agent control and evaluation visible in an interview. A future adapter can import a broader data platform without changing the application contract.

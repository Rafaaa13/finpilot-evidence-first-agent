# FinPilot v0.3 interview / STAR companion

Use this as a truthful speaking guide. Do not add real-data, user, or model metrics until you have a run log.

## 90 seconds

**Situation.** Financial research tools often mix retrieval, arithmetic, portfolio rules and narrative. The result may be fluent but not auditable: a candidate can be excluded without a reason, a filing can be used before disclosure, or a model can rewrite a number.

**Task.** I built FinPilot to make a local, reproducible research-preparation workflow. The first vertical slice is investment research: validate a cutoff and CSV snapshot, screen candidates, construct a capped long-only research portfolio, stress it on common dates, and export an evidence-linked memo. The same workbench includes credit risk, model-validation, fixed-income and option tools for finance-role preparation.

**Action.** I separated deterministic computation from optional language understanding. The local core handles CSV schema, single-currency checks, PE/growth/margin/leverage rules, data freshness, point-in-time exclusions, portfolio weights, cash, common-date returns and three stress scenarios. Each row carries source/date/evidence metadata. LLM access is explicit opt-in: it can select existing finding IDs and create diligence questions, but cannot calculate, rewrite, or approve a financial number.

**Result.** The project runs locally without an LLM or live provider and exports a user-oriented workbench and research memo. The repository has offline tests for investment screening, portfolio caps, date alignment, stress insufficiency, CSV errors, MCP transport and LLM schemas. The data is synthetic or user-provided and not independently verified, so I do not present it as investment performance, alpha, regulatory validation or user impact.

## Product walkthrough

First show the Investment Research page. Explain that the user is not asked to learn the architecture before seeing the value. The screen answers four questions: what passed, what was excluded, why, and what evidence supports the row. Switch the allocation method and show that the weight rule changes while the screening data stays fixed. Point out that a hard cap can leave cash.

Then show the stress cards. Explain that the system intersects real dates before computing returns; if the common sample is too short, it stops. The historical scenario is a current-weight diagnostic, not a trading backtest. Open the evidence ledger and memo export.

Finally open the LLM panel. Enter a question, show the send preview, and explain that only summarized findings and the question are eligible for model context. The offline checklist remains available if no model is configured.

## Deep answers

**Why not make it a trading agent?** A trade-execution product requires real-time providers, corporate actions, liquidity, costs, permissions, compliance and operational controls. This project deliberately solves the earlier research-preparation problem and exposes the boundary rather than hiding it.

**Why use an absolute score?** The score is a transparent heuristic to rank a small research queue. It is not a cross-sectional alpha model or a calibrated forecast. Absolute thresholds make the demo hand-checkable and make missing data visible.

**Why preserve cash?** A position cap is a risk constraint. If the eligible universe cannot fill the portfolio without violating it, silently relaxing the cap would be a product and risk-control bug. Cash makes the constraint observable.

**Why common dates?** Positional concatenation can combine returns from different market days and create false covariance. The risk engine intersects dates first, calculates returns second, and fails closed when the overlap is too small.

**What does the LLM improve?** It improves question understanding, finding relevance, diligence prompts and language. It does not improve the truth of raw financial numbers. That is why it is an enhancement layer, not the product's source of truth.

## Evidence to collect personally

Before using stronger resume language, personally hand-check one PE, one portfolio-weight and one stress calculation; modify at least three parameters; inject a future filing, duplicate price and too-short history; run the test suite; save the command, input hash, result hash, expected value, actual value, difference and conclusion. For user research, recruit and consent separately; do not put private interview notes in GitHub.

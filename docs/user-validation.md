# User validation protocol

This document is a protocol, not evidence that validation has occurred.

## Recruit and permissions

Recruit people who perform junior research, risk, data-governance or financial-product tasks. Explain that the prototype uses synthetic data, is not investment advice and records only task outcomes and approved feedback. Obtain consent before recording. Do not upload names, employer details, private files or verbatim sensitive interview material to GitHub.

## Task script

Ask the participant to review one historical-date research case and one credit-stress case. The control can use a spreadsheet or a short scripted baseline; the treatment uses the FinPilot evidence and risk views. Give the same data, assumptions and time limit. Do not teach the treatment answer during the task. Ask the participant to state which numbers they trust, where they would check, and when they would stop.

## Measures

Primary measures are task completion rate, unsupported-claim detection rate, numeric correction rate and time to a defensible answer. Guardrails are reviewer over-trust, failed evidence checks, latency, cost and frustration. Record a structured rubric with pass/fail and short rationale; never turn a small convenience sample into a population claim.

## Bad cases to inject

Use at least one filing whose filed date is after the requested as-of date, one unknown unit, one missing evidence locator, one duplicate observation, one high drawdown, one capped stressed PD, one bond shock and one malformed model claim. The desired result is review or blocked, not an attractive complete memo.

## Analysis plan

Before data collection, define the primary metric and exclusion rules. Report numerator, denominator, task wording, participant background at a coarse level, and all failures. Keep control and treatment results paired where possible. Do not report a percentage without the sample size and do not claim causality from an uncontrolled demonstration.

## Current status

No external interviews, user acceptance tests or user outcome metrics have been completed for this repository. The only valid current evidence is the offline code and its reproducible tests.

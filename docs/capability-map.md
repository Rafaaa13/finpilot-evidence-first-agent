# FinPilot capability map

## AI product track

| Capability | FinPilot evidence | What is still missing before claiming it as experience |
| --- | --- | --- |
| Problem framing | Product scope, non-goals, review states and user scenarios in `docs/product.md` | External user interviews and a signed-off PRD |
| AI workflow design | Resolver, data steward, analysts, risk officer, skeptic and writer trace | A real model call with cost/latency log and failure cases |
| Tool and data contracts | Observation/Evidence/Claim schemas, point-in-time gate, strict JSON | A live provider adapter tested against an approved endpoint |
| Evaluation | Hand-check tests, leakage gate, numeric consistency and offline cases | Frozen model benchmark, blind human scoring and bad-case taxonomy |
| Safety | Read-only boundary, no arbitrary shell/SQL, fail-closed language | Threat-model review and secret-scanning/CI evidence |
| Product analytics | Event dictionary and validation protocol | Real event data, SQL output, funnel and retention evidence |
| Delivery | Runnable CLI, report artifacts, local server | Peer review, user acceptance and deployment runbook |

## Finance track

| Role family | Evidence | Interview point |
| --- | --- | --- |
| Risk management / model validation | PD/LGD/EAD stress, EAD-weighted EL, chronological validation, AUC/Brier/ECE caveats | Explain why synthetic metrics are code checks, not regulatory validation |
| Financial infrastructure / data governance | Raw references, source locators, units, filed/effective dates, strict serialization | Explain lineage, schema validation and what happens when data is missing |
| ALM / fixed income / markets | Bond price, duration, convexity, DV01 and parallel yield shock | Explain price-yield inverse relationship and approximation error |
| Fintech / risk product | User scenario, risk gate, evidence ledger, review state and local read-only server | Explain how a control becomes a product requirement and an acceptance test |

## Interview-safe vocabulary

Use “implemented and tested” only for code paths with tests and a reproduced run. Use “designed” for the live data and model adapter until it has been connected and tested. Use “planned” for user interviews, external UAT, deployment and model benchmark. Use “AI-assisted development” if that is how the code was produced, and personally reproduce the arithmetic before making a stronger claim.

## SQL practice draft

Once an event table exists, these are practice queries rather than existing product metrics:

```sql
-- review rate by run mode
SELECT mode,
       COUNT(*) AS runs,
       SUM(CASE WHEN status = 'review' THEN 1 ELSE 0 END) * 1.0 / COUNT(*) AS review_rate
FROM runs
WHERE started_at >= :start_date
GROUP BY mode;

-- evidence coverage by run
SELECT run_id,
       AVG(CASE WHEN evidence_count > 0 THEN 1.0 ELSE 0.0 END) AS cited_claim_rate
FROM claims
GROUP BY run_id;

-- most common failure states
SELECT error_code, COUNT(*) AS occurrences
FROM run_events
WHERE status IN ('blocked', 'review', 'error')
GROUP BY error_code
ORDER BY occurrences DESC;
```

The SQL must not be presented as measured product analytics until the event schema, timestamps, access permissions and actual rows exist.

## Product experiment template

Hypothesis: an evidence ledger lowers unsupported-claim rate without making review time unacceptable. Control: deterministic memo without visible claim-level evidence. Treatment: same memo with evidence IDs, formula references and review warnings. Primary metrics: unsupported-claim rate and human correction rate. Guardrails: task failure rate, latency, cost and reviewer confidence. Stop if the treatment hides missing data or causes reviewers to accept unsupported claims.

## Financial experiment template

Question: how sensitive is portfolio EL to PD and LGD assumptions? Freeze the 240-loan synthetic corpus and chronological split. Sweep PD multiplier and LGD shift. Report total EAD, expected loss amount/rate, incremental loss, top exposure share and HHI. Do not choose a favorable scenario or call it a real lender forecast. For the bond case, sweep parallel yield shocks and compare exact price change with duration-only and duration-plus-convexity approximations.

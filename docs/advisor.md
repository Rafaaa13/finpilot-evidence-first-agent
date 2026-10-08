# Optional LLM advisor boundary

FinPilot's local investment core does not need a model. The advisor is a separate enhancement layer for a researcher who wants to ask a natural-language question about an already-computed run.

## Local-first path

Without an endpoint, the advisor returns a deterministic checklist: data provenance, valuation comparability, earnings quality, leverage, concentration and risk-history questions. This is immediately usable and costs nothing.

## Model path

When `FINPILOT_LLM_ENDPOINT` is configured, the workbench can show a send preview and make an explicit request. The context contains the user question, data label, as-of date, and a compact list of existing finding IDs and texts. It does not include raw CSV text, private documents, keys, or arbitrary tool access.

The model may return only existing finding IDs and question IDs. It cannot create a number, alter an existing number, select a new tool, call shell/SQL/network, or turn a synthetic source into a verified source. Unknown IDs, duplicate IDs, malformed JSON and oversized outputs fall back to the local checklist and are marked in the trace.

A successful connection test proves only transport and JSON response. It does not prove financial accuracy. Before using a real provider, review its data retention, model training, regional processing, key handling, rate limits and billing.

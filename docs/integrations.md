# Integration guide

The offline pipeline does not call external models or provider servers. `integrations.py` contains optional adapter primitives only. No SEC/Yahoo MCP or live model has been connected, installed or benchmarked in this delivery.

## Explicit data providers

`data_sources.py` now provides offline `data doctor`, local `UserSnapshotProvider`, lazy opt-in `YFinanceProvider`, and a bounded raw-companyfacts `SecEdgarProvider` wrapper. It does not invoke the legacy cached `_get_json`, guess ticker mappings, derive accounting ratios, or silently fall back to synthetic data. Both network and terms consent are required; SEC additionally requires explicit CIK and real contact user-agent. The adapters have injected mock tests only: no live provider was called or installed for this implementation. Fetch results remain `verified=false`. See [data-sources.md](data-sources.md).

## Local MCP

Start from `config/mcp.example.json`. Review the chosen server source, license, data terms, endpoint privacy, credentials and tool schema before filling an explicit command list. Never paste a shell pipeline into the command field. Discover the server's actual tool names with `tools/list`, then allowlist only approved read-only tools. FinPilot must not infer tool names from marketing descriptions.

The stdio client implements JSON-RPC initialization, a tool list request and a bounded allowlisted tool call. Provider output must be mapped into the normalized Observation contract. Unknown units, missing required fields and inconsistent dates should be rejected rather than guessed. A live provider error must not silently become synthetic fixture output.

## Optional model

A caller may instantiate `LlmClient` or set `FINPILOT_LLM_ENDPOINT`, `FINPILOT_LLM_MODEL` and `FINPILOT_LLM_API_KEY` in its environment. Keys are not read from a browser and must not be committed. Send only approved public or synthetic summaries, not private reports, resumes or raw customer documents.

The draft endpoint is OpenAI-compatible `/chat/completions`. It requests structured claims with evidence IDs and rejects malformed JSON, oversized claim lists and unknown evidence IDs. This syntactic gate is not a semantic guarantee: a human must still inspect whether each citation actually supports the text. Numeric calculations and point-in-time checks stay in deterministic tools.

## Before calling it production ready

Use a sanitized recorded server response to test mapping, verify timeout/response-size limits, test process exit and invalid IDs, simulate schema drift, verify unit and date handling, and record actual model token usage and latency. Freeze test cases before comparing prompts. Do not call protocol mocks a live integration benchmark.

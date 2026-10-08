# FinPilot data sources and real-case workflow

## Default is safe and reproducible

`python -m finpilot research` and the existing Python APIs remain offline and deterministic. The bundled `DEMO01`–`DEMO08` records are synthetic. The existing CSV import remains the preferred way to use an authorized real snapshot:

```bash
python -m finpilot data doctor --provider user_snapshot \
  --stocks /path/to/stocks.csv --prices /path/to/prices.csv --as-of 2025-12-31
python -m finpilot research --as-of 2025-12-31 \
  --stocks /path/to/stocks.csv --prices /path/to/prices.csv
```

The local-CSV research command saves `research.json` plus a separate `input-manifest.json` under `--output` (default `reports/research`). The original deterministic `content_hash` belongs to the research payload; the separate manifest retains input provenance rather than altering the old API/hash contract.

`data doctor` is offline. It validates the existing CSV contract, reports optional dependency availability, and never downloads, installs, writes a provider cache, or converts a failure into the synthetic fixture.

## Optional provider adapters

`src/finpilot/data_sources.py` adds dependency-injected adapters without changing the old `investment.py`, `portfolio.py`, `data.py`, or `integrations.py` APIs.

### yfinance

Install it separately only if the user has reviewed the terms and is authorized to use the source. The repository's normal install does not install it:

```bash
python -m finpilot data doctor --provider yfinance
python -m finpilot fetch --provider yfinance --ticker AAPL \
  --start 2024-01-01 --end 2024-12-31 \
  --allow-network --accept-terms \
  --output /tmp/aapl-provider.json --prices-output /tmp/aapl-prices.csv
```

The adapter imports `yfinance` only during the explicit fetch path, requests inclusive date bounds, requires `Adj Close` rather than silently substituting `Close`, validates positive finite values, and does not persist responses or secrets. `--prices-output` is only a conversion to the legacy `prices.csv` shape; keep the JSON manifest beside it.

### SEC raw companyfacts

Use an explicit CIK and a real contact user-agent. The wrapper does not guess ticker-to-CIK and does not turn raw facts into TTM/EPS/FCF or a `stocks.csv` row:

```bash
python -m finpilot fetch --provider sec_edgar --ticker AAPL --cik 0000320193 \
  --start 2024-01-01 --end 2024-12-31 \
  --user-agent 'Research Team contact@your-domain.example' \
  --allow-network --accept-terms --output /tmp/sec-facts.json
```

The wrapper uses an injected/bounded HTTP transport, rejects redirects and oversized/non-JSON/wrong-company responses, filters raw facts by `filed` date, retains accession numbers, and does not cache the response. Current companyfacts can contain amendments and restatements; a filed-date filter is not a historical response vintage.

### Common output contract

Provider output carries:

- `data_kind=real_user_fetch` for opt-in external fetches;
- `verified=false` and `verification_status=not_independently_verified`;
- request date bounds, provider locator, normalized/raw hashes where available, and warnings;
- no API keys, contact user-agent, cookies, or raw secrets in the manifest;
- explicit failures. There is no provider-to-fixture fallback.

A successful HTTP response proves transport and parsing only. It does not prove data accuracy, accounting interpretation, source licensing, corporate-action treatment, or investment suitability.

## Public case snapshots

`examples/real_cases/historical_reference_snapshots.json` contains a small set of cited public historical reference points. `examples/real_cases/financial_casebook.json` contains official-public facts for Apple FY2024, Microsoft FY2024, NVIDIA FY2024 and WTI April 2020. These are citation-bearing case facts, not a redistributed market database or a verified investment dataset. Derived margins and hypothetical P&L are FinPilot calculations and are labelled as such.


`examples/real_cases/` contains four metadata-only templates:

- `case_2022_01_rate_shock.json`
- `case_2020_03_pandemic_shock.json`
- `case_2022_tech_valuation_downturn.json`
- `case_single_company_filing_quality.json`

Each has `data_status=user_snapshot_required`, official source links, research questions, required CSV fields, and reproduction notes. They contain no precise market numbers or built-in real-company snapshots; they are practice templates until the researcher supplies an authorized snapshot. See [`examples/real_cases/README.md`](../examples/real_cases/README.md).

## Verification boundary

A source string, official URL, provider name, successful request, or normalized hash is provenance, not independent verification. Human review must still check source terms, company identity, ticker/CIK mapping, units, currencies, adjustment convention, period/filling dates, amendments/restatements, and whether the requested question is answerable from the available vintage.

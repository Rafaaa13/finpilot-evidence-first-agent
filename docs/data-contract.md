# FinPilot investment data contract

## Purpose

This contract supports a local research snapshot, not an official market-data feed. The user remains responsible for source licensing, accuracy, accounting definitions and corporate-action treatment. FinPilot labels imported records as `user_import` / `用户提供，未独立核验` unless the input is the bundled synthetic demo.

## `stocks.csv`

The header must be exactly:

```text
symbol,name,sector,currency,price_as_of,price,eps_ttm,revenue_growth,operating_margin,fcf_margin,debt_to_equity,period_end,filed_at,source
```

`symbol` is an uppercase research identifier of up to 15 characters. `currency` must be a three-letter code and the entire file must use one currency. `price` and `eps_ttm` are currency per share under the user's stated accounting convention. `revenue_growth`, `operating_margin` and `fcf_margin` are decimal ratios, not percentage strings. `debt_to_equity` is a multiple. `period_end` must not be later than `filed_at`; both must not be later than `as_of` for a record to pass the point-in-time gate.

## `prices.csv`

The header must be exactly:

```text
date,symbol,adj_close
```

`adj_close` must be a positive user-supplied adjusted price. Duplicate symbol/date rows are rejected. Dates after `as_of` are excluded. Price history is used only for descriptive volatility, momentum, drawdown and current-weight stress diagnostics. It is not a forecast and is not a trading execution record.

## Missing and stale data

Missing financial metrics exclude a row from the relevant rule-based screen rather than becoming zero. A price snapshot more than 120 days old or a filing more than 550 days old is marked stale. A price series with fewer than 41 observations or a gap larger than seven days produces a warning; common-date risk with fewer than 40 returns becomes `insufficient`.

## Evidence

Each row creates an evidence entry containing the source string, filing date, period end, price date, input record and a raw hash. A source string is provenance metadata, not independent verification. The output includes `data_kind`, `data_label`, `input_hash`, `content_hash`, trace steps and a memo so a reviewer can reproduce what the system saw.

## Optional fetch contract

The separate `data_sources.py` adapters do not change this CSV schema or verify it. A fetch returns `provider-result-v1`, `data_kind=real_user_fetch`, `verified=false`, `verification_status=not_independently_verified`, explicit request bounds, provider location, fetch time, hashes and warnings. `ProviderResult.prices_csv()` / CLI `--prices-output` converts only the adjusted prices to the legacy header; retain the JSON provenance beside the CSV. Research after local re-import is still `user_import`, not independently verified. SEC output is raw companyfacts, not a `stocks.csv` generator: filing selection, TTM, units, accounting definitions and revisions remain human responsibilities. See [data sources](data-sources.md).

Versioned case metadata in `examples/real_cases/` uses `data_status=user_snapshot_required`. Official links are reference entry points, not bundled verified snapshots, precise market numbers or redistribution permission.

## Deliberate scope

The current rules are most interpretable for non-financial companies. Banks, insurers, REITs, commodity producers and companies with unusual accounting require industry-specific fields and should not be judged by this generic screen without human review.

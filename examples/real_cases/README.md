# Real-data cases

This folder has two different kinds of cases and they must not be confused.

## Cited public snapshots included in the repository

`historical_reference_snapshots.json` contains a small S&P 500/Treasury reference set. `financial_casebook.json` contains four public-source financial/event cases: Apple FY2024, Microsoft FY2024, NVIDIA FY2024 and WTI April 2020. `historical_reference_snapshots.md` and `financial_casebook.md` explain the source and what the numbers can and cannot prove.

These snapshots are enough to let a user click through a real, source-linked case without first starting a provider. They are sparse facts, not a live security database, complete daily histories, or a redistribution license for source providers.

## Metadata-only practice templates

The `case_*.json` files are `user_snapshot_required` templates. They are intentionally useful for a high-end researcher who wants to bring an authorized CSV snapshot, but they do not pretend to contain real company prices.

## Recommended workflow

For a beginner, start in the static workbench and select the public historical case. For a professional, obtain an authorized snapshot, run `data doctor`, keep the provider manifest, and call `research --stocks ... --prices ...`. If using `fetch`, pass both network and terms opt-ins; a provider result remains `verified=false`.

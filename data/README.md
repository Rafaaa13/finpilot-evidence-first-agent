# Data inventory

This folder is the small, distributable public-data layer. It is separate from user-import snapshots and optional network fetches.

`public/world_bank_gdp_growth_2018_2023.csv` is a frozen extraction of World Bank indicator `NY.GDP.MKTP.KD.ZG` for the United States, China, Japan and Germany, downloaded/read on 2026-10-06 from the public API response. Every row keeps the source URL and snapshot update date. Values are annual GDP growth percentages; they are macro context, not stock returns or a recommendation.

`public/world_bank_cpi_growth_2018_2023.csv` contains World Bank indicator `FP.CPI.TOTL.ZG` for the same four countries and years; `public/world_bank_exports_pct_gdp_2018_2023.csv` contains `NE.EXP.GNFS.ZS`. These are small macro context tables, not securities prices. Source URLs, indicator codes, snapshot date and units are retained in each row.

The World Bank indicator metadata pages identify these WDI indicators as CC BY-4.0. Keep the source URL, indicator code and snapshot date when redistributing; re-check the current terms before commercial use. The tables were read from the public API response on 2026-10-06 and are frozen snapshots, not automatic updates.

`public/sp500_shiller_monthly_2018_2023.csv` is a 72-row monthly slice of the `datasets/s-and-p-500` public dataset, sourced from Robert Shiller's historical data and later FRED price-only extensions. It includes S&P 500 level, dividend, earnings, CPI, long rate and CAPE fields. The upstream repository applies ODC-PDDL 1.0 but notes that original-source licensing should be checked; retain attribution and verify current terms before redistribution or commercial use. Rows after 2023-06 are price-only extensions, so zero dividend/earnings/CAPE fields are not measured zeros.

The S&P 500, Treasury, Apple, Microsoft, NVIDIA and WTI case files contain additional cited reference points, not a full investable price history. Full security research should use an authorized CSV snapshot or the explicit opt-in provider commands.

Do not put private snapshots under `data/public/`. Put user-authorized files under a local ignored directory such as `data/snapshots/` or pass them directly to the CLI.

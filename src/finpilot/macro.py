"""Small, distributable public macro-data catalog.

The files are frozen extracts with source URLs in every row. This module never
contacts a network and never treats macro context as security-level data.
"""
from __future__ import annotations
import csv
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
_PUBLIC = _ROOT / "data" / "public"
_FILES = {
    "gdp_growth": ("world_bank_gdp_growth_2018_2023.csv", "GDP growth (annual %)", "NY.GDP.MKTP.KD.ZG"),
    "cpi_growth": ("world_bank_cpi_growth_2018_2023.csv", "Inflation, consumer prices (annual %)", "FP.CPI.TOTL.ZG"),
    "exports_pct_gdp": ("world_bank_exports_pct_gdp_2018_2023.csv", "Exports of goods and services (% of GDP)", "NE.EXP.GNFS.ZS"),
}


def load_public_macro() -> dict[str, Any]:
    datasets = []
    for dataset_id, (filename, label, indicator) in _FILES.items():
        path = _PUBLIC / filename
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise ValueError(f"public macro dataset is empty: {filename}")
        required = {"dataset_id", "country", "iso3", "year", "source_url", "snapshot_updated"}
        if not required.issubset(rows[0]):
            raise ValueError(f"public macro dataset schema invalid: {filename}")
        parsed = []
        for row in rows:
            year = int(row["year"]); value_key = next(k for k in row if k not in required)
            value = float(row[value_key])
            parsed.append({"country": row["country"], "iso3": row["iso3"], "year": year, "value": value, "source_url": row["source_url"], "snapshot_updated": row["snapshot_updated"]})
        datasets.append({"dataset_id": dataset_id, "indicator": indicator, "label": label, "unit": "percent", "rows": parsed, "data_kind": "public_snapshot", "verified": False, "license_note": "World Bank public data; verify current license/attribution terms before redistribution or commercial use."})
    return {"schema_version": "public-macro-v1", "data_status": "public_snapshot", "datasets": datasets, "caveat": "Macro context only; not a security price, forecast, or investment recommendation."}


def macro_latest(country: str = "United States") -> list[dict[str, Any]]:
    catalog = load_public_macro()
    output = []
    for dataset in catalog["datasets"]:
        matches = [row for row in dataset["rows"] if row["country"] == country]
        if matches:
            latest = max(matches, key=lambda row: row["year"])
            output.append({"dataset_id": dataset["dataset_id"], "label": dataset["label"], **latest})
    return output

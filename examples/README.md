# FinPilot local import examples

These two files are synthetic and intentionally labelled with `demo://synthetic/...` sources. They are for testing the local import path, not real securities or market data.

```bash
python -m finpilot serve
```

Then use the Investment Research page to upload `stocks_demo.csv` and `prices_demo.csv`. The screen, portfolio and stress result should match the bundled offline demo. Replace them only with data you are authorized to use and keep the source, currency, accounting convention, filing date and price adjustment method documented.

The [`real_cases/`](real_cases/) directory is different: it contains versioned metadata-only research exercises with `data_status=user_snapshot_required`. Those templates reference official source entry points but bundle no real-company or exact market numbers. See its README before supplying an authorized snapshot.

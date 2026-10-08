# 官方公开财务案例库

`financial_casebook.json` contains four small public-source cases with exact figures and links. The values are not a complete company dataset, are not a live market feed, and are not independently audited by FinPilot.

## Apple FY2024

Use to discuss profit quality and one-time items. The case includes FY2024 net sales, net income, tax provision and approximate one-time tax charge. FinPilot derives net margin and one-time charge / net income. It intentionally does not include price, shares, segment forecasts or a target price.

## Microsoft FY2024

Use to discuss revenue, operating income and operating leverage. The case derives operating margin, then asks which segment, capex, cash-flow and competition evidence is still needed.

## NVIDIA FY2024

Use to discuss exceptional growth, high margins, concentration and valuation normalization. The case derives operating and net margin but does not turn those figures into a forecast.

## WTI April 2020

Use to discuss futures contract mechanics, storage, liquidity, expiry and negative settlement. It is not a spot-price or trading-strategy example. The hypothetical P&L calculator in `cases.py` requires the user to specify entry price, contracts, contract size and margin; those are assumptions, not historical portfolio results.

Sources are stored inside each case JSON. Review the source terms before redistributing any larger dataset.

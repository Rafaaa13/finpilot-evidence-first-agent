# FinPilot model and data card

## Intended use

FinPilot is an educational prototype for exploring evidence-linked financial research, credit-risk arithmetic, fixed-income sensitivity and AI product controls. It is intended for software demonstrations, interview discussion and personal study. It is not intended for investment decisions, lending decisions, regulatory reporting, model approval, trade execution or customer-facing advice.

## Data

The default fixture is generated locally with fixed seeds. Market and filing-shaped observations are synthetic and are labelled as such. The credit portfolio contains 240 synthetic loans with generated PD, LGD, EAD and sampled default fields. None of these values represents a borrower, issuer, security, filing or market outcome.

A future live provider may use public SEC or market-data services, but no live provider is assumed to be connected by this repository. Provider terms, rate limits, data completeness, restatements and licensing must be reviewed separately.

## Methods

The system calculates deterministic ratios and risk measures. The composite score is a descriptive heuristic. The credit validation metrics are code-level demonstrations on synthetic data and do not demonstrate calibration. Fixed-income metrics use standard periodic cash-flow assumptions. Black–Scholes assumes a European option with lognormal dynamics and constant parameters; Monte Carlo is a numerical check, not a valuation opinion. The momentum backtest is a single educational execution path with explicit next-close lag and proportional transaction cost.

## Limitations and risks

The fixture is not representative. The sample is small and generated. There is no proof of predictive performance, external validity, fairness, regulatory compliance, production reliability, data freshness, or user benefit. The current repository contains no external user study or live model-quality benchmark. A model adapter, if later added, must not be allowed to change numeric results or bypass evidence and risk gates.

## Human oversight

Any high-impact financial interpretation requires a qualified human reviewer. A missing source, unknown unit, future observation, incompatible tool output, malformed model response or inadequate sample should result in review or abstention.

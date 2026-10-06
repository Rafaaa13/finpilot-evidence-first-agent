# Contributing to FinPilot

FinPilot favors small, reviewable changes with explicit data and model boundaries. Please include tests for financial arithmetic, date visibility, serialization, or failure states. Do not add real customer data, keys, private interview material, or copied proprietary documents.

For financial changes, include the formula, units, assumptions, and at least one independent hand-check. For provider changes, include a sanitized fixture and state the source terms, caching and rate-limit behavior. For model changes, document the allowed input/output schema and how unsupported claims are rejected.

Run `python -m unittest discover -s tests -v` and `git diff --check` before opening a pull request. Do not report fixture results as live-market performance.

# FinPilot publish checklist

## Before the first public push

Create a fresh repository that contains only FinPilot, not the selected computer folders or private source documents. Confirm that no file contains personal resumes, private financial-agent research, interview notes, client data, model keys, browser credentials or generated live-data caches. Keep the synthetic fixture visibly labelled in the README and reports.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
python -m finpilot demo --ticker AAPL --as-of 2025-12-31 --output /tmp/finpilot-demo
python -m finpilot risk --output /tmp/finpilot-risk.json
python -m finpilot eval --output /tmp/finpilot-eval.json
python -m json.tool /tmp/finpilot-risk.json >/dev/null
python -m json.tool /tmp/finpilot-eval.json >/dev/null
git diff --check
```

Review the generated memo and JSON manually. Check that the point-in-time gate is true, result hash is present, run ID is unique, non-finite values are null, and no output implies real AAPL data or investment performance.

## Repository setup

```bash
git init
git add README.md README.en.md LICENSE pyproject.toml .env.example .gitignore src tests docs .github
 git status --short
 git commit -m "Build evidence-first financial research cockpit"
 git branch -M main
git remote add origin <your-empty-github-repository-url>
git push -u origin main
```

Do not include a generated report unless it is deliberately reviewed and kept as a clearly synthetic example. If generated artifacts are included for the portfolio page, regenerate them from the exact committed code and record the command.

## Public presentation

The README should lead with the problem and a screenshot or terminal run, then show the data contract, evidence ledger, risk tools, evaluation boundaries and quick start. A small contribution guide and issue templates are more credible than claims about popularity. GitHub stars cannot be guaranteed; quality is improved by reproducibility, readable issues, a focused scope, and honest limitations.

## External data and MCP

No external server should be called merely because a config file exists. Before connecting SEC/Yahoo MCP, review the server license, provider terms, endpoint privacy, user-agent/rate limits, tool names, response schema, timeout, caching, key handling and read-only allowlist. Add a provider-specific integration test with a saved sanitized fixture before describing live access in a resume.

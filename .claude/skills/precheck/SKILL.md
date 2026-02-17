---
name: precheck
description: Run pre-commit checks and frontend lint to validate code before pushing
---

Run the project's quality checks. Determine scope from arguments or default to staged files.

## Backend (Python)

For staged files only:
```bash
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml
```

For all files (matches CI):
```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
```

## Frontend

```bash
cd frontend && npm run lint:fix && npm run build
```

## Rules
- If any check fails, fix the issues and re-run
- Report which hooks passed and which failed
- For Ruff errors, auto-fix with `ruff check --fix` where possible
- Never skip pre-commit hooks with `--no-verify`

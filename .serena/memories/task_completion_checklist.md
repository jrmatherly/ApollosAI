# Task Completion Checklist

When a coding task is completed, run through the following:

## Backend Changes
1. Run linting: `pre-commit run --config ./dev_config/python/.pre-commit-config.yaml`
   - If it fails, it may auto-fix some issues. Re-run until clean.
   - Common issues: Mypy type errors, Ruff formatting, trailing whitespace, missing newlines
2. Run relevant unit tests: `poetry run pytest tests/unit/test_xxx.py`
3. Stage specific files: `git add <specific-files>` (never `git add .`)

## Frontend Changes
1. Run lint + fix: `cd frontend && npm run lint:fix`
2. Run build: `cd frontend && npm run build`
3. Run tests if applicable: `cd frontend && npm run test`
4. Check i18n if new strings added: `npm run make-i18n`

## Enterprise Changes
1. Run enterprise linting: `poetry run pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml`
2. Run enterprise tests: `PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest --forked -n auto -s ./enterprise/tests/unit`

## VSCode Extension Changes
1. Lint: `cd openhands/integrations/vscode && npm run lint:fix`
2. Compile: `npm run compile`

## General
- Ensure no secrets (.env, credentials) are staged
- Pre-commit hooks must pass before push
- Follow PR template when creating pull requests

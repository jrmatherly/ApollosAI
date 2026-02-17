---
name: code-reviewer
description: Reviews recently modified code for style violations, type errors, and architectural concerns
tools: Read, Glob, Grep, Bash
---

Review the recently modified files (from `git diff --name-only`) for:

1. **Python style**:
   - Ruff violations (config at `dev_config/python/ruff.toml`)
   - Type hint style: use `list[X]`, `X | Y`, `X | None` — never `List`, `Union`, `Optional`
   - Single quotes for inline strings, double quotes for docstrings
   - No `AppMode.OSS` usage (use `AppMode.OPENHANDS`)

2. **Frontend style**:
   - TanStack Query data flow: components must not call API services directly
   - All user-facing strings must use i18n (`useTranslation` / `t()`)
   - ESLint airbnb-typescript compliance

3. **Enterprise**:
   - Relative imports without `enterprise.` prefix
   - Alembic migration has both `upgrade()` and `downgrade()`

4. **General**:
   - No secrets or API keys in code
   - No `git add .` or `git add -A` patterns
   - No files from `third_party/` modified without good reason

Report issues with `file_path:line_number` references. Be concise — only flag real problems.

# VSCode Lint Settings — Targeted Gap-Fill Design

**Date**: 2026-02-17
**Status**: Approved
**Scope**: `.vscode/settings.json` update to enforce lint rules during development

## Problem

The project has specific linting rules enforced by pre-commit hooks and CI, but the
VSCode settings don't fully align. Developers fix lint violations after the fact
(during commit or CI) instead of seeing/fixing them during development.

## Gaps Identified

| Gap | CI Enforcement | Current VSCode |
|-----|---------------|----------------|
| Ruff auto-fix on save | `ruff check --fix --unsafe-fixes` | Code actions set to `"explicit"` (manual) |
| Pylance type checking | mypy with `strict_optional`, `warn_redundant_casts`, `warn_unreachable` | No type checking mode configured |
| Pylance exclusions | mypy excludes `third_party/`, `enterprise/` | No exclusions configured |
| ESLint discovery | `eslint.config.js` in `frontend/` | No `workingDirectories` — ESLint may not find config |
| ESLint auto-fix | `eslint src --fix` in CI | No `source.fixAll.eslint` on save |
| Line length guidance | Ruff formats at 88 columns (default) | No editor rulers |

## Design

### 1. Ruff Code Actions (Python)

Change `source.fixAll.ruff` and `source.organizeImports.ruff` from `"explicit"` to
`"always"`. This auto-applies lint fixes and import sorting on every save.

Additionally, add `unsafe-fixes = true` to `dev_config/python/ruff.toml` so the
VSCode extension applies the same unsafe fixes that pre-commit does (pre-commit runs
`ruff check --fix --unsafe-fixes`). Without this, the editor only applies safe fixes
and developers still see pre-commit modifying files at commit time.

### 2. Pylance Type Checking

- Set `python.analysis.typeCheckingMode` to `"basic"`
- Exclude `third_party` and `enterprise` (matches mypy.ini `exclude`)
- Add `diagnosticSeverityOverrides` for:
  - `reportOptionalMemberAccess`, `reportOptionalCall`, `reportOptionalIterable`,
    `reportOptionalSubscript` — all `"warning"` (matches mypy `strict_optional`)
  - `reportUnnecessaryCast` — `"warning"` (matches mypy `warn_redundant_casts`)
  - `reportUnusedImport` — `"warning"` (matches Ruff F401)

Note: `reportUnreachable` is already enabled in Pylance's "basic" mode (matches
mypy `warn_unreachable`).

### 3. ESLint Configuration

- Add `eslint.workingDirectories: ["./frontend"]` — tells the extension that
  `frontend/` contains the `eslint.config.js` flat config
- ESLint 9 flat config is auto-detected by the extension (`useFlatConfig` defaults
  to `true` for ESLint 9)

Note: `eslint.options.overrideConfigFile` is intentionally NOT used because it
would double-path when combined with `workingDirectories` (the extension already
resolves the config relative to the working directory).

### 4. ESLint Auto-Fix on Save

Add `source.fixAll.eslint: "always"` to the `[typescript][typescriptreact]...`
scope. On save:
1. ESLint auto-fix runs (import ordering, unused imports, code quality)
2. Prettier formats the result (spacing, trailing commas)

This matches CI: `eslint src --fix && prettier --write`.

### 5. Python Rulers

Add `editor.rulers: [88]` in the `[python]` scope. Ruff's default line length is 88
(no explicit `line-length` in `ruff.toml`). This shows where Ruff's **formatter**
wraps lines — it is NOT a lint enforcement boundary (E501 is disabled in ruff.toml).
The ruler provides visual guidance for keeping code readable.

## Files Changed

- `.vscode/settings.json` — 5 targeted additions/modifications
- `dev_config/python/ruff.toml` — add `unsafe-fixes = true` (enables parity with pre-commit)

## Known Gaps

These gaps cannot be closed with VSCode settings alone:

1. **`no_implicit_optional`**: mypy.ini sets `no_implicit_optional = True` (disallows
   `def f(x: int = None)` — requires `x: int | None = None`). Pylance has no
   equivalent diagnostic. Mypy via pre-commit remains the only gate for this.

2. **Pylance vs mypy parity**: Pylance "basic" mode is a reasonable approximation but
   not equivalent to mypy. Some mypy errors will not appear in Pylance and vice versa.
   Mypy via pre-commit is the authoritative type checker.

## What This Does NOT Change

- No new extensions (all recommended extensions already listed in `extensions.json`)
- No multi-root workspace conversion
- No DX-only enhancements (file nesting, bracket colorization, etc.)
- No changes to ESLint, mypy, or Prettier config files

## References

- [VSCode ESLint Extension](https://github.com/microsoft/vscode-eslint) — `workingDirectories` for monorepos
- [ESLint Flat Config Docs](https://eslint.org/docs/latest/use/configure/configuration-files) — config file discovery
- Pre-commit config: `dev_config/python/.pre-commit-config.yaml`
- Ruff config: `dev_config/python/ruff.toml`
- Mypy config: `dev_config/python/mypy.ini`
- ESLint config: `frontend/eslint.config.js`
- Prettier config: `frontend/.prettierrc.json`

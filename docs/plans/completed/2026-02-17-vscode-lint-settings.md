# VSCode Lint Settings Gap-Fill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update `.vscode/settings.json` so linting rules are enforced during development, not just at commit/CI time.

**Architecture:** Edit `.vscode/settings.json` (5 targeted changes) and `dev_config/python/ruff.toml` (1 addition). Closes gaps between VSCode behavior and pre-commit/CI enforcement. No new files, no new extensions.

**Tech Stack:** VSCode settings JSON, Ruff extension, Pylance, ESLint extension, Prettier extension.

**Design doc:** `docs/plans/2026-02-17-vscode-lint-settings-design.md`

---

### Task 1: Ruff auto-fix on save

**Files:**
- Modify: `.vscode/settings.json:25-32` (the `[python]` block)

**Step 1: Change Ruff code actions from explicit to always**

In `.vscode/settings.json`, find the `[python]` block and change:

```json
"[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.rulers": [88],
    "editor.codeActionsOnSave": {
        "source.fixAll.ruff": "always",
        "source.organizeImports.ruff": "always"
    }
},
```

Changes from current:
- `"source.fixAll.ruff"`: `"explicit"` → `"always"`
- `"source.organizeImports.ruff"`: `"explicit"` → `"always"`
- Added `"editor.rulers": [88]` — shows where `ruff format` wraps lines (NOT a lint boundary; E501 is disabled)

**Step 2: Enable unsafe fixes in ruff.toml**

In `dev_config/python/ruff.toml`, add at the top level (before `[lint]`):

```toml
unsafe-fixes = true
```

This enables the Ruff VSCode extension to apply the same unsafe fixes that pre-commit
does (pre-commit passes `--unsafe-fixes` on the command line). Without this, the editor
only applies safe fixes and developers still see pre-commit modifying files at commit.

**Step 3: Verify JSON is valid**

Run: `python -m json.tool .vscode/settings.json > /dev/null`

Note: This file uses JSONC (comments), so use VSCode's built-in validation instead — open the file and check for red squiggles. Or strip comments first: `grep -v '^\s*//' .vscode/settings.json | python -m json.tool > /dev/null`

**Step 4: Commit**

```bash
git add .vscode/settings.json dev_config/python/ruff.toml
git commit -m "chore(vscode): auto-fix Ruff lint + imports on save with unsafe-fixes"
```

---

### Task 2: Pylance type checking

**Files:**
- Modify: `.vscode/settings.json:23-24` (insert after `packageIndexDepths` block, before `[python]` block)

**Step 1: Add Pylance type checking settings**

Insert the following block between the `packageIndexDepths` array (line 23) and the `// ── Python Formatting` comment (line 24):

```json
// ── Pylance Type Checking (approximates mypy.ini) ─────────────
"python.analysis.typeCheckingMode": "basic",
"python.analysis.exclude": [
    "third_party",
    "enterprise"
],
"python.analysis.diagnosticSeverityOverrides": {
    "reportOptionalMemberAccess": "warning",
    "reportOptionalCall": "warning",
    "reportOptionalIterable": "warning",
    "reportOptionalSubscript": "warning",
    "reportUnnecessaryCast": "warning",
    "reportUnusedImport": "warning"
},
```

**Why each override:**
- `reportOptional*` → matches mypy.ini `strict_optional = True`
- `reportUnnecessaryCast` → matches mypy.ini `warn_redundant_casts = True`
- `reportUnusedImport` → matches Ruff rule F401
- `exclude` → matches mypy.ini `exclude = (third_party/|enterprise/)`

**Step 2: Commit**

```bash
git add .vscode/settings.json
git commit -m "chore(vscode): add Pylance type checking matching mypy.ini"
```

---

### Task 3: ESLint monorepo configuration

**Files:**
- Modify: `.vscode/settings.json:33-34` (insert after `ruff.configuration` line, before `// ── TypeScript` comment)

**Step 1: Add ESLint working directory and config path**

Insert the following block between `ruff.configuration` (line 33) and `// ── TypeScript` (line 34):

```json
// ── ESLint (flat config in frontend/) ──────────────────────────
"eslint.workingDirectories": ["./frontend"],
```

**Why:**
- `workingDirectories` tells the ESLint extension that `frontend/` is the working
  directory where `eslint.config.js` lives
- ESLint 9 flat config auto-detection is already enabled by default
- Note: `overrideConfigFile` is intentionally NOT used — it would double-path when
  combined with `workingDirectories` (the extension resolves config relative to the
  working directory)

**Step 2: Commit**

```bash
git add .vscode/settings.json
git commit -m "chore(vscode): configure ESLint working directory for monorepo"
```

---

### Task 4: ESLint auto-fix on save for TS/JS

**Files:**
- Modify: `.vscode/settings.json:38-41` (the `[typescript][typescriptreact]...` block)

**Step 1: Add ESLint code actions on save**

Update the frontend formatter block to include ESLint auto-fix:

```json
"[typescript][typescriptreact][javascript][javascriptreact]": {
    "editor.defaultFormatter": "esbenp.prettier-vscode",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.fixAll.eslint": "always"
    }
},
```

Change from current: added the `editor.codeActionsOnSave` block with `source.fixAll.eslint`.

**Save order:** ESLint auto-fix runs first (import ordering, unused imports), then Prettier formats. Matches CI: `eslint src --fix && prettier --write`.

**Step 2: Commit**

```bash
git add .vscode/settings.json
git commit -m "chore(vscode): auto-fix ESLint violations on save for TS/JS"
```

---

### Task 5: Final validation

**Step 1: Verify the complete file is valid JSONC**

Open `.vscode/settings.json` in VSCode and verify:
- No red squiggles (syntax errors)
- All comment blocks are properly formatted
- Settings are grouped logically with section headers

**Step 2: Functional smoke test**

1. Open a Python file (e.g., `openhands/core/config/__init__.py`)
   - Verify Ruff diagnostics appear inline
   - Add a trailing space, save — verify it's auto-removed
   - Add `from typing import List`, save — verify Ruff auto-fixes to `list`

2. Open a TypeScript file (e.g., `frontend/src/App.tsx` or any component)
   - Verify ESLint diagnostics appear inline
   - Verify Prettier formats on save

3. Check Pylance diagnostics
   - Open a Python file — verify type warnings appear for Optional access patterns
   - Verify no diagnostics appear for files in `third_party/` or `enterprise/`

**Step 3: Squash or leave as separate commits**

If desired, squash tasks 1-4 into a single commit:
```bash
git rebase -i HEAD~4
# Squash into: "chore(vscode): align settings with CI lint rules"
```

Or leave as 4 granular commits for reviewability.

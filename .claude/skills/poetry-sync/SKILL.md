---
name: poetry-sync
description: Validate poetry.lock sync with pyproject.toml and regenerate if stale
disable-model-invocation: true
---

Validate and fix poetry.lock synchronization with pyproject.toml.

## Steps

1. **Check lock sync**:
   ```bash
   poetry check --lock 2>&1
   ```
   - If output contains "changed significantly" → lock is stale, proceed to step 2
   - If only warnings (duplicate fields from dual PEP 621 + Poetry sections) → lock is fine, report success and stop

2. **Regenerate lock file**:
   ```bash
   poetry lock
   ```
   This takes ~30-60s (571 packages). Do NOT use `poetry lock --no-update` — it does not exist in Poetry 2.x.

3. **Verify sync**:
   ```bash
   poetry check --lock 2>&1
   ```
   Confirm no "changed significantly" error remains.

4. **Report result**:
   - If fixed: "poetry.lock regenerated and in sync. Remember to `git add poetry.lock` before committing."
   - If already in sync: "poetry.lock is already in sync with pyproject.toml."

## Context

- `pyproject.toml` has TWO dependency sections (PEP 621 + Poetry) — both affect the content hash
- The `pyproject-fmt` pre-commit hook reformats `pyproject.toml`, which can invalidate the lock even for metadata-only changes
- CI (`py-tests.yml`) runs `poetry install` which fails if the lock hash is stale

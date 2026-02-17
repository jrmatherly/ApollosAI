---
name: new-migration
description: Create a new Alembic migration for the enterprise database schema
disable-model-invocation: true
---

Create a new enterprise Alembic migration. Takes a description as argument.

## Steps

1. **Find the latest migration number**:
   ```bash
   ls enterprise/migrations/versions/ | sort | tail -5
   ```

2. **Determine the next sequential number** (e.g., if latest is `092.py`, next is `093.py`)

3. **Read the latest migration** to follow the existing pattern for imports, revision ID format, and structure

4. **Generate the migration** with:
   ```bash
   cd enterprise && PYTHONPATH=".:$PYTHONPATH" poetry run alembic revision -m "description_here"
   ```
   Or create it manually following the existing pattern.

5. **Ensure both `upgrade()` and `downgrade()` are implemented** — never create a migration without a downgrade path

6. **Validate** the migration:
   ```bash
   cd enterprise && PYTHONPATH=".:$PYTHONPATH" poetry run alembic check
   ```

## Rules
- Follow the sequential numbering convention in `enterprise/migrations/versions/`
- Use relative imports (no `enterprise.` prefix)
- Always include `downgrade()` that fully reverses the `upgrade()`
- Test with: `PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest tests/unit/ -k migration`

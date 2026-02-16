# Code Style & Conventions

## Python Backend

### Formatting & Linting
- **Formatter**: Ruff (v0.12.5)
- **Linter**: Ruff + Mypy (v1.17)
- **Config**: `dev_config/python/ruff.toml`, `dev_config/python/mypy.ini`
- **Quote Style**: Single quotes for inline, double quotes for docstrings
- **Line Length**: No E501 enforcement (no strict line length limit)
- **Docstrings**: Google convention (ruff D rules)

### Type Hints
- Modern Python type hints: `list[X]` over `List[X]`, `X | Y` over `Union[X, Y]`, `X | None` over `Optional[X]`
- Mypy: `check_untyped_defs=True`, `strict_optional=True`, `no_implicit_optional=True`

### Import Rules
- Ruff I (isort) rules enabled for import sorting
- Enterprise code uses relative imports without `enterprise.` prefix

### Pre-commit Hooks
- trailing-whitespace, end-of-file-fixer, check-yaml, debug-statements
- Ruff check + format
- Mypy type checking
- pyproject-fmt, validate-pyproject
- Custom: warn on `AppMode.OSS` usage (prefer `AppMode.OPENHANDS`)

## Frontend (TypeScript/React)

### Formatting & Linting
- **Linter**: ESLint (airbnb-typescript config)
- **Formatter**: Prettier
- **Type Checking**: TypeScript strict mode via `tsc`

### Architecture Patterns
- **Data Fetching**: TanStack Query (React Query) — never call API directly from components
- **Data Flow**: UI Components → TanStack Query hooks → Data Access Layer (`src/api/`) → API
- **Query Hooks**: `use[Resource]` pattern (e.g., `useConversationSkills`)
- **Mutation Hooks**: `use[Action]` pattern (e.g., `useDeleteConversation`)
- **State**: Zustand for client state, TanStack Query for server state
- **Settings**: Entity-based (immediate save) vs Form-based (manual save) patterns

### I18n
- All user-facing strings must be internationalized
- Run `npm run make-i18n` after adding translation keys

## Git Conventions
- Use specific `git add <filename>` instead of `git add .`
- Pre-commit hooks MUST pass before pushing
- PR template at `.github/pull_request_template.md`

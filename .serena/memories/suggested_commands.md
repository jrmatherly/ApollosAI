# Suggested Commands

## Full Build
```bash
make build                  # Build entire project (backend + frontend + hooks)
```

## Backend Development
```bash
# Install Python dependencies
poetry install --with dev,test

# Run backend linting (staged files)
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml

# Run backend linting (all files)
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml

# Run unit tests
poetry run pytest tests/unit/test_xxx.py

# Install pre-commit hooks
make install-pre-commit-hooks

# Run full application
export INSTALL_DOCKER=0
export RUNTIME=local
make build && make run FRONTEND_PORT=12000 FRONTEND_HOST=0.0.0.0 BACKEND_HOST=0.0.0.0
```

## Frontend Development
```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Dev with mock API
npm run dev:mock

# Lint and fix
npm run lint:fix

# Build for production
npm run build

# Run tests
npm run test

# Generate i18n declarations
npm run make-i18n

# Type checking
npm run typecheck
```

## Enterprise Development
```bash
cd enterprise

# Install enterprise dependencies
poetry install --with dev,test

# Run enterprise tests
PYTHONPATH=".:$PYTHONPATH" poetry run --project=enterprise pytest --forked -n auto -s ./enterprise/tests/unit --cov=enterprise

# Run specific module tests
PYTHONPATH=".:$PYTHONPATH" poetry run pytest tests/unit/telemetry/ --confcutdir=tests/unit/telemetry

# Start enterprise backend
make start-backend

# Enterprise linting
poetry run pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
```

## ApollosAI Development
```bash
# Set dev env vars (auth bypass mode)
export APOLLOSAI_ALLOW_UNAUTHENTICATED=true
export JWT_SECRET=dev-secret-at-least-32-characters-long
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apollosai_dev
export APOLLOSAI_ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

# Run ApollosAI server
python -m apollosai.bootstrap   # Sets OPENHANDS_CONFIG_CLS
make start-backend

# Run ApollosAI tests
poetry run pytest tests/unit/test_apollosai*.py -v

# Run specific module tests
poetry run pytest tests/unit/test_apollosai_auth.py -v

# Run with coverage
poetry run pytest tests/unit/test_apollosai*.py --cov=apollosai --cov-branch

# Alembic migrations (uses apollosai-specific config)
cd apollosai && alembic -c alembic.ini upgrade head
cd apollosai && alembic -c alembic.ini revision --autogenerate -m "description"
```

## Git
```bash
git fetch upstream && git rebase upstream/<branch>    # Sync with upstream
git add <specific-file>                               # Stage specific files (preferred over git add .)
```

## System (macOS / Darwin)
```bash
git, ls, cd, grep, find    # Standard unix tools available on macOS
brew                         # Package manager (if installed)
```

# Getting Started with ApollosAI

ApollosAI is an automated AI software engineer platform built on OpenHands. This guide walks you through setup from scratch.

## Prerequisites

| Dependency | Version | Check |
|------------|---------|-------|
| Python | 3.12+ (< 3.14) | `python3.12 --version` |
| Node.js | >= 22.12.0 | `node --version` |
| npm | (bundled with Node) | `npm --version` |
| Poetry | >= 1.8 | `poetry --version` |
| Docker | latest | `docker --version` |
| PostgreSQL | 12+ | `psql --version` |
| Git | latest | `git --version` |
| tmux | (optional) | `tmux -V` |

### Installing Prerequisites

**Python 3.12** (macOS):
```bash
brew install python@3.12
```

**Node.js 22+** (via nvm):
```bash
nvm install 22
nvm use 22
```

**Poetry**:
```bash
curl -sSL https://install.python-poetry.org | python3.12 -
# Add Poetry to your PATH per the installer output
```

**Docker**: Download from [docker.com](https://www.docker.com/products/docker-desktop/).

**PostgreSQL** (macOS):
```bash
brew install postgresql@16
brew services start postgresql@16
```

## 1. Clone the Repository

```bash
git clone https://github.com/jrmatherly/ApollosAI.git
cd ApollosAI
```

## 2. Build the Project

The `make build` target validates all prerequisites, installs dependencies, and builds the frontend:

```bash
make build
```

This runs:
1. **Dependency checks** — Python, Node.js, npm, Docker, Poetry
2. **Python dependencies** — `poetry install --with dev,test,runtime` (571 packages)
3. **Frontend dependencies** — `cd frontend && npm install`
4. **Pre-commit hooks** — Installs ruff, mypy, trailing whitespace checks
5. **Frontend build** — `cd frontend && npm run build`

### Manual Steps (if `make build` isn't suitable)

```bash
# Python
poetry env use python3.12
poetry install --with dev,test,runtime

# Frontend
cd frontend && npm install && npm run build && cd ..

# Pre-commit hooks
poetry run pre-commit install --config ./dev_config/python/.pre-commit-config.yaml
```

## 3. Configure Environment

### 3a. Environment Variables (.env)

Bootstrap from the provided example:

```bash
make setup-env
# Creates .env from .env.example
```

Then edit `.env` with your values:

```bash
# .env — Required variables
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/apollosai
JWT_SECRET=<your-secret-minimum-32-characters>
APOLLOSAI_ENCRYPTION_KEY=<your-base64-key>

# Dev mode: skip Entra ID auth
APOLLOSAI_ALLOW_UNAUTHENTICATED=1

# CORS for frontend dev server
APOLLOSAI_CORS_ORIGINS=http://localhost:3001
```

Generate secrets:

```bash
# JWT secret (64-char hex)
openssl rand -hex 32

# Encryption key (base64)
openssl rand -base64 32
```

For the full environment variable reference, see [docs/environment-variables.md](environment-variables.md).

### 3b. LLM Configuration (config.toml)

Run the interactive setup:

```bash
make setup-config
```

Or create a minimal `config.toml` manually:

```toml
[core]
workspace_base = "./workspace"

[llm]
model = "gpt-5-mini"
api_key = "your-api-key-here"
```

See `config.template.toml` for the complete configuration reference with all available options.

## 4. Database Setup

Create the PostgreSQL database:

```bash
createdb apollosai
# Or with a specific user:
# createdb -U postgres apollosai
```

Run migrations:

```bash
make migrate
```

Check migration status:

```bash
make migrate-status
```

## 5. Run the Application

### Development (backend + frontend)

```bash
make run
```

This starts:
- **Backend**: ApollosAI server on `http://localhost:3000`
- **Frontend**: Vite dev server on `http://localhost:3001`

### Backend Only

```bash
make start-apollosai
```

The backend runs with auto-reload, watching `apollosai/` and `openhands/` directories.

### Frontend Only

```bash
make start-frontend
```

### Frontend with Mocked Backend (no backend required)

```bash
cd frontend
npm run dev:mock        # OSS mode mocks
npm run dev:mock:saas   # SaaS mode mocks (with billing)
```

## 6. Verify Installation

1. Open `http://localhost:3001` in your browser
2. The frontend should load the ApollosAI interface
3. Check backend health at `http://localhost:3000/api/v1/health` (if health routes are configured)

Run the test suite to confirm everything works:

```bash
# ApollosAI unit tests (391 tests)
make test-apollosai

# Frontend tests
make test-frontend

# All backend tests
make test-backend
```

## Docker Deployment

### Build Images

```bash
# Standard app image
make docker-build-app

# Enterprise image (includes apollosai/ layer)
make docker-build-ent
```

### Run with Docker Compose

```bash
# Set workspace directory
export WORKSPACE_BASE=$(pwd)/workspace

# Start
docker compose up
```

The app will be available at `http://localhost:3000`.

### Develop Inside Docker

```bash
make docker-dev
```

## Project Structure

```
ApollosAI/
  openhands/             # Core AI agent engine (Python)
  apollosai/             # Enterprise auth, integrations, monitoring
  frontend/              # React/TypeScript frontend
  enterprise/            # Enterprise features (Polyform license)
  tests/                 # Test suite (pytest)
  containers/            # Docker build configs
  config.template.toml   # Runtime configuration reference
  .env.example           # Environment variable template
  Makefile               # Build, run, test, lint targets
```

## Common Tasks

### Lint Before Committing

```bash
# Backend (must pass before push — CI runs --all-files)
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml

# Frontend
cd frontend && npm run lint:fix && npm run build
```

### Create a Database Migration

```bash
make migrate-create MSG='add user preferences table'
# Then fix ruff formatting:
pre-commit run --all-files --config ./dev_config/python/.pre-commit-config.yaml
```

### Run Specific Tests

```bash
# Single test file
poetry run pytest tests/unit/apollosai/server/test_branding.py -v

# Tests matching a pattern
poetry run pytest tests/unit/apollosai/ -k "test_replay" -v

# With coverage
make test-apollosai-cov
```

### Work in an Isolated Branch

```bash
git worktree add .worktrees/my-feature -b feature/my-feature
cd .worktrees/my-feature
poetry install
mkdir -p frontend/build && touch frontend/build/index.html  # stub for imports
```

## Make Targets Reference

| Target | Description |
|--------|-------------|
| `make build` | Full build (deps + frontend + hooks) |
| `make run` | Run backend + frontend |
| `make start-apollosai` | Backend only (with auto-reload) |
| `make start-frontend` | Frontend dev server only |
| `make test` | ApollosAI + frontend tests |
| `make test-apollosai` | ApollosAI unit tests |
| `make test-backend` | All backend tests (parallel) |
| `make test-frontend` | Frontend tests (vitest) |
| `make lint` | All linters (backend + frontend) |
| `make migrate` | Run Alembic migrations |
| `make migrate-create MSG='...'` | Create new migration |
| `make migrate-status` | Check migration status |
| `make setup-config` | Interactive LLM config |
| `make setup-env` | Bootstrap .env |
| `make docker-build-app` | Build ApollosAI Docker image (unified) |
| `make docker-build-ent` | Alias for docker-build-app |
| `make docker-run` | Run via Docker Compose |
| `make clean` | Remove caches |
| `make help` | Show all targets |

## Environment Variables Reference

### Required

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string (`postgresql+asyncpg://...`) |
| `JWT_SECRET` | JWT signing secret (min 32 chars) |
| `APOLLOSAI_ENCRYPTION_KEY` | AES-256-GCM master key (`openssl rand -base64 32`) |

### Required (Production — Entra ID Auth)

| Variable | Description |
|----------|-------------|
| `ENTRA_TENANT_ID` | Microsoft Entra ID tenant |
| `ENTRA_CLIENT_ID` | OAuth2 client ID |
| `ENTRA_CLIENT_SECRET` | OAuth2 client secret |
| `ENTRA_REDIRECT_URI` | OAuth2 callback URL |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `APOLLOSAI_ALLOW_UNAUTHENTICATED` | `false` | Skip auth (dev only, parsed: `1`/`true`/`yes`) |
| `APOLLOSAI_CORS_ORIGINS` | `http://localhost:3001` | Comma-separated CORS origins |
| `SESSION_SECRET` | `JWT_SECRET` | Starlette SessionMiddleware secret |
| `FRONTEND_DIRECTORY` | `./frontend/dist` | Path to built frontend |
| `REDIS_URL` | (disabled) | Redis for rate limiting |

## Troubleshooting

### `make run` fails with ".env file not found"

```bash
make setup-env
# Edit .env with your database URL and secrets
```

### Poetry install fails

```bash
# Ensure Python 3.12 is available
poetry env use python3.12
poetry install --with dev,test,runtime
```

### Frontend build fails with Node version error

```bash
# Requires Node.js >= 22.12.0
node --version
nvm install 22
nvm use 22
```

### Database connection refused

```bash
# Start PostgreSQL
brew services start postgresql@16  # macOS
sudo systemctl start postgresql    # Linux

# Create the database
createdb apollosai
```

### Pre-commit hooks fail

```bash
# Run all-files to catch everything
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml

# If poetry.lock is stale after pyproject.toml changes:
poetry lock
```

### Tests fail in a worktree

```bash
cd .worktrees/my-feature
poetry install                    # Fresh venv in worktrees
mkdir -p frontend/build && touch frontend/build/index.html  # Stub for imports
```

## Next Steps

- Read `CLAUDE.md` for code style conventions and architecture details
- Read `AGENTS.md` for agent development procedures
- Read `config.template.toml` for all runtime configuration options
- Read `docs/environment-variables.md` for the full env var reference
- Run `make help` to see all available Makefile targets

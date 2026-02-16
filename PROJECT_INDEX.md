# Project Index: ApollosAI (OpenHands)

Generated: 2026-02-16 | v1.3.0 | Python 3.12+ | React 19 | TypeScript

## Project Structure

```
openhands/           460 .py  - Python backend (AI agent engine)
  agenthub/                   - Agent implementations (6 agents)
  app_server/                 - V1 application server (SDK-based)
  controller/                 - Agent control loop & state machine
  core/                       - Config, messages, exceptions
  events/                     - Event system (actions + observations)
  llm/                        - LLM provider interface (LiteLLM)
  memory/                     - History condensation (8+ strategies)
  mcp/                        - Model Context Protocol integration
  runtime/                    - Sandboxed execution (Docker/K8s/Local)
  server/                     - V0 FastAPI HTTP server
  storage/                    - File backends (Local/S3/GCS)
frontend/src/        726 files - React/TypeScript frontend
  api/                        - 16 typed API services
  hooks/                      - 100+ TanStack Query/Mutation hooks
  components/                 - 28 feature component directories
  stores/                     - 15 Zustand stores
  routes/                     - React Router 7 (23 route files)
  types/                      - V0 + V1 type systems
enterprise/          406 .py  - Enterprise features (Polyform license)
  integrations/               - 8 platforms (GitHub/GitLab/Jira/Linear/Slack)
  storage/                    - 74 DB models/stores (PostgreSQL)
  migrations/                 - 92 Alembic versions
  server/                     - 17 API route modules
tests/               204 .py  - Test suite
  unit/                       - Unit tests (pytest)
  e2e/                        - End-to-end tests
  runtime/                    - Runtime/sandbox tests
```

## Entry Points

- **CLI**: `openhands/` package with `openhands.core` config
- **Backend API**: `openhands/server/app.py` (V0), `openhands/app_server/v1_router.py` (V1)
- **Frontend**: `frontend/src/entry.client.tsx` via React Router
- **Enterprise**: `enterprise/saas_server.py` (extends core server)
- **Docker**: `containers/app/Dockerfile` (multi-stage: Node+Python)
- **Config**: `config.template.toml` (all runtime options)

## Core Modules

### Backend (Python)
- `core/config/` - OpenHandsConfig (agent, LLM, sandbox, security, MCP, condenser)
- `events/` - 11 action types + 15 observation types, EventStream pub-sub
- `controller/` - AgentController loop, Agent base class (registry pattern), State
- `agenthub/` - CodeActAgent (production), Browsing, VisualBrowsing, ReadOnly, LOC, Dummy
- `llm/` - LLM/AsyncLLM/StreamingLLM, LLMRegistry, Metrics, ModelFeatures
- `runtime/` - Docker, Kubernetes, Local, Remote, CLI runtimes
- `memory/condenser/` - NoOp, Window, Recent, LLMSummarizing, Attention, Pipeline
- `storage/` - FileStore: Local, S3, GoogleCloud, InMemory, WebHook
- `mcp/` - MCPClient, tool conversion, tool execution

### Frontend (TypeScript/React)
- `api/` - Axios-based services: conversation, git, settings, billing, auth, events
- `hooks/query/` - 57 query hooks (`use[Resource]` pattern)
- `hooks/mutation/` - 43 mutation hooks (`use[Action]` pattern)
- `stores/` - Zustand: conversation, agent, home, status, metrics, browser, events
- `types/core/` - Event types with 40+ type guards, V0/V1 parallel systems
- `components/` - chat (50 files), settings (32 dirs), home (15 dirs), sidebar, controls

## Configuration

- `config.template.toml` - [core], [llm], [agent], [sandbox], [security], [condenser], [kubernetes], [mcp]
- `dev_config/python/ruff.toml` - Ruff linter (single quotes, Google docstrings)
- `dev_config/python/mypy.ini` - Mypy (strict optional, check untyped defs)
- `dev_config/python/.pre-commit-config.yaml` - Pre-commit hooks (ruff, mypy, trailing-ws)
- `frontend/.env` - VITE_BACKEND_HOST, VITE_USE_TLS, VITE_FRONTEND_PORT

## Quick Start

```bash
make build                    # Full build (backend + frontend + hooks)
make run                      # Run application (port 3000)

# Backend
poetry install --with dev,test
poetry run pytest tests/unit/test_xxx.py
pre-commit run --config ./dev_config/python/.pre-commit-config.yaml

# Frontend
cd frontend && npm install
npm run dev                   # Dev server
npm run lint:fix && npm run build
npm run test                  # Vitest
```

## Key Dependencies

- `litellm>=1.74.3` - Multi-provider LLM gateway
- `fastapi` + `uvicorn` - HTTP server
- `sqlalchemy[asyncio]>=2.0.40` + `asyncpg` - Database
- `react@19` + `react-router@7` - Frontend framework
- `@tanstack/react-query@5` - Data fetching/cache
- `zustand@5` - Client state management
- `tailwindcss@4` + `@heroui/react` - UI/styling
- `socket.io-client` - Real-time WebSocket
- `docker` + `kubernetes>=33.1` - Container orchestration

## Key Patterns

- **Registry**: Agents self-register via `Agent.register()`
- **Pub-Sub**: EventStream central hub for all inter-component events
- **Factory**: `get_file_store()`, runtime selection
- **Strategy**: Pluggable condenser implementations
- **Query/Mutation**: TanStack hooks wrap all API calls (never call API from components)
- **Type Guards**: 40+ predicates for runtime event discrimination

## Conventions

- Python: single quotes, `X | None` not `Optional[X]`, Google docstrings
- Frontend: ESLint airbnb-ts + Prettier, i18n all strings
- Git: `git add <file>` not `git add .`, pre-commit must pass
- Deprecated: `AppMode.OSS` -> use `AppMode.OPENHANDS`

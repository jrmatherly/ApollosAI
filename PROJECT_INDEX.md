# Project Index: ApollosAI (OpenHands)

Generated: 2026-02-18 | v1.3.0 | Python 3.12+ | React 19 | TypeScript

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
frontend/src/        884 files - React/TypeScript frontend
  api/                        - 24 typed API services
  hooks/                      - 111 TanStack Query/Mutation hooks
  components/                 - Feature components (chat, settings, admin, home, sidebar)
  stores/                     - 15 Zustand stores
  routes/                     - React Router 7 (31 route files)
  types/                      - V0 + V1 type systems
enterprise/          406 .py  - Enterprise features (Polyform license)
  integrations/               - 8 platforms (GitHub/GitLab/Jira/Linear/Slack)
  storage/                    - 74 DB models/stores (PostgreSQL)
  migrations/                 - 92 Alembic versions
  server/                     - 17 API route modules
apollosai/            99 .py  - ApollosAI enterprise layer
  server/                     - Config, auth (Entra ID), routes (9 modules), lifespan
  storage/                    - PostgreSQL models, stores, encryption
  integrations/               - 5 platforms (GitHub/Jira/Slack/Bitbucket/Microsoft)
  monitoring/                 - OTEL, audit logging, health probes
  mcp/                        - MCP server configuration
  migrations/                 - Alembic versions (separate from enterprise)
tests/               278 .py  - Test suite (391 unit tests)
  unit/                       - Unit tests (pytest)
  e2e/                        - End-to-end tests
  runtime/                    - Runtime/sandbox tests
```

## Entry Points

- **CLI**: `openhands/` package with `openhands.core` config
- **Backend API**: `openhands/server/app.py` (V0), `openhands/app_server/v1_router.py` (V1)
- **Frontend**: `frontend/src/entry.client.tsx` via React Router
- **Enterprise**: `enterprise/saas_server.py` (extends core server)
- **ApollosAI**: `apollosai/app_server.py` (enterprise auth entry point)
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

### ApollosAI Enterprise Layer (`apollosai/`)
- `server/config.py` - ApollosAIServerConfig (extends ServerConfig, app_mode=SAAS)
- `server/auth/` - Entra ID OAuth2, JWT sessions, MSAL client, auth errors
- `server/auth/user_context.py` - EntraIDUserContextInjector (V0->V1 bridge)
- `server/routes/` - auth, admin, health, integrations, mcp, models, orgs, teams, api_keys
- `server/lifespan.py` - ApollosAILifespanService (custom startup/shutdown)
- `integrations/base.py` - ApollosAIIntegrationManager (ABC with replay protection, payload sanitization)
- `integrations/` - GitHub, Jira, Slack, Bitbucket, Microsoft (typed views, HMAC validation)
- `integrations/registry.py` - IntegrationRegistry (register/lookup by IntegrationType)
- `monitoring/otel.py` - OpenTelemetry setup (traces, metrics, logging)
- `monitoring/audit.py` - Structured audit logging for admin actions
- `monitoring/health.py` - Liveness/readiness probes
- `monitoring/listener.py` - EventStream listener for OTEL span creation
- `mcp/config.py` - MCP server CRUD configuration
- `storage/` - PostgreSQL models (user, org, team, role, api_key, auth_token), encrypted fields
- `storage/database.py` - Async SQLAlchemy engine (auto-converts postgres:// URLs)
- `storage/encrypt_utils.py` - AES-256-GCM field encryption (HKDF key derivation)
- `migrations/` - Alembic versions (separate from enterprise/migrations/)
- `bootstrap.py` - Sets OPENHANDS_CONFIG_CLS if not overridden
- `app_server.py` - Entry point for ApollosAI server

### Frontend (TypeScript/React)
- `api/` - 24 Axios-based services: conversation, git, settings, billing, auth, events, admin, mcp-admin, integration
- `hooks/query/` - 61 query hooks (`use[Resource]` pattern)
- `hooks/mutation/` - 50 mutation hooks (`use[Action]` pattern)
- `hooks/` - Utility hooks: use-branding, use-settings-nav-items, use-current-org-id
- `stores/` - Zustand: conversation, agent, home, status, metrics, browser, events
- `types/core/` - Event types with 40+ type guards, V0/V1 parallel systems
- `components/features/admin/` - 8 admin components (members, integrations, MCP, audit, roles)
- `components/features/settings/` - Settings provenance, nav items
- `components/features/` - chat (50 files), home (15 dirs), sidebar, controls
- `routes/admin-*.tsx` - 8 admin routes (members, integrations, MCP, audit, alerts, API keys, models, teams)
- `constants/settings-nav.tsx` - SAAS/OSS/APOLLOSAI nav item sets
- `i18n/` - 14-language translations, declaration.ts enum

## Configuration

- `config.template.toml` - [core], [llm], [agent], [sandbox], [security], [condenser], [kubernetes], [mcp]
- `dev_config/python/ruff.toml` - Ruff linter (single quotes, Google docstrings)
- `dev_config/python/mypy.ini` - Mypy (strict optional, check untyped defs)
- `dev_config/python/.pre-commit-config.yaml` - Pre-commit hooks (ruff, mypy, trailing-ws)
- `frontend/.env` - VITE_BACKEND_HOST, VITE_USE_TLS, VITE_FRONTEND_PORT
- `docs/environment-variables.md` - ApollosAI enterprise env var reference

## Quick Start

```bash
make build                    # Full build (backend + frontend + hooks)
make run                      # Run application (port 3000)
make start-apollosai          # ApollosAI backend only
make test-apollosai           # Run 391 ApollosAI unit tests
make migrate                  # Run Alembic migrations

# Backend
poetry install --with dev,test
poetry run pytest tests/unit/test_xxx.py
pre-commit run --all-files --config ./dev_config/python/.pre-commit-config.yaml

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

- **Registry**: Agents self-register via `Agent.register()`; integrations via `IntegrationRegistry`
- **Pub-Sub**: EventStream central hub for all inter-component events
- **Factory**: `get_file_store()`, runtime selection
- **Strategy**: Pluggable condenser implementations
- **Query/Mutation**: TanStack hooks wrap all API calls (never call API from components)
- **Type Guards**: 40+ predicates for runtime event discrimination
- **Env Var Getters**: Lazy `get_*()` functions prevent import-time caching (apollosai auth)
- **V0/V1 Bridge**: `EntraIDUserContextInjector` wraps V0 `EntraIDUserAuth` into V1 `UserContext`
- **Replay Protection**: Base manager dedup cache (OrderedDict, instance-level, 10k max)
- **Payload Sanitization**: `sanitize_payload()` redacts sensitive keys before storage
- **Fail-Closed Webhooks**: Missing signing secrets reject by default; `APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS` opt-in
- **ApollosAI Mode**: Frontend `isSaasMode && !isBillingEnabled` → distinct nav/branding

## Conventions

- Python: single quotes, `X | None` not `Optional[X]`, Google docstrings
- Frontend: ESLint 9 flat config + Prettier, i18n all strings (14 languages required)
- Git: `git add <file>` not `git add .`, pre-commit must pass
- Deprecated: `AppMode.OSS` -> use `AppMode.OPENHANDS`

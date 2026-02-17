# Architecture Overview

## Control Flow
User -> Server (FastAPI) -> AgentController (loop) -> Agent (step) -> LLM (LiteLLM)
AgentController -> Runtime (execute actions) -> EventStream (central pub-sub)
EventStream -> Memory, Server, State, Storage subscribers

## Backend Modules
- **core/**: Config management (OpenHandsConfig, AgentConfig, LLMConfig, SandboxConfig, etc.)
- **events/**: Event system — 11 action types, 15+ observation types, EventStream pub-sub
- **controller/**: Agent control loop, state machine, stuck detection
- **agenthub/**: 6 agents — CodeActAgent (production), Browsing, VisualBrowsing, ReadOnly, LOC, Dummy
- **llm/**: LLM interface via LiteLLM, LLMRegistry, Metrics, retry/debug mixins
- **runtime/**: Sandboxed execution — Docker, Kubernetes, Local, Remote, CLI
- **memory/**: History condensation — 8+ condenser strategies, PipelineCondenser
- **storage/**: File backends — Local, S3, GCS, InMemory, WebHook
- **mcp/**: Model Context Protocol client/tool integration
- **server/**: V0 FastAPI routes (conversations, files, git, settings, etc.)
- **app_server/**: V1 server using Software Agent SDK

## Frontend Structure
- **api/**: 16 typed API services (conversation, git, settings, billing, etc.)
- **hooks/**: 57 query hooks + 43 mutation hooks via TanStack Query
- **stores/**: 15 Zustand stores (conversation, agent, home, status, etc.)
- **components/**: 28 feature directories + shared + ui
- **routes/**: React Router 7 with nested layouts (home, conversation, settings, etc.)
- **types/**: V0 + V1 type systems with 40+ type guards

## Enterprise
- 8 platform integrations (GitHub, GitLab, Jira, Jira DC, Linear, Slack, Bitbucket, Solvability)
- 74 storage models, 95 Alembic migrations
- 17 API route modules (auth, billing, orgs, integrations, etc.)
- Abstract Manager pattern for integrations

## ApollosAI Enterprise Layer (`apollosai/`)
Sits between OpenHands core and the enterprise module. Provides Entra ID OAuth2, JWT sessions, RBAC, CRUD routes, and encrypted PostgreSQL storage. Phase 1/1.5 (PR #1) + Phase 2 (PR #5) merged to main.

- **server/config.py**: `ApollosAIServerConfig` — extends `ServerConfig`, sets `app_mode=AppMode.SAAS`, `enable_v1=True`
- **server/auth/entraid_auth.py**: `EntraIDUserAuth` — V0 auth handler (JWT cookie + Bearer token + API key)
- **server/auth/user_context.py**: `EntraIDUserContextInjector` — V0->V1 bridge into `UserContext`
- **server/auth/jwt_utils.py**: JWT creation/validation with `aud: 'apollosai'` + `jti` claims, `validate_session_token()` for revocation
- **server/auth/rbac.py**: `require_auth()`, `require_role()` FastAPI dependencies, `PermissionDeniedError`
- **server/auth/constants.py**: Env var getters (lazy, not import-cached)
- **server/db_session.py**: `ApollosAIDbSessionInjector` — V1 `Injector[AsyncSession]`
- **server/deps.py**: FastAPI `Depends(get_db_session)` for route-level DB access
- **server/lifespan.py**: `ApollosAILifespanService` — async engine init, session maker, skips OpenHands migrations
- **server/rate_limit.py**: `slowapi` limiter (Redis backend if `REDIS_URL` set)
- **server/middleware/db_session_middleware.py**: DB-backed server-side sessions (replaces cookie sessions)
- **server/routes/auth.py**: `/auth/login`, `/auth/callback`, `/auth/logout` (with MSAL signout)
- **server/routes/orgs.py**: Organization CRUD with RBAC
- **server/routes/teams.py**: Team CRUD with RBAC
- **server/routes/api_keys.py**: API key create/list/revoke
- **server/routes/models.py**: Pydantic request/response models
- **storage/models/**: 12 SQLAlchemy models (user, org, team, role, memberships, api_key, auth_token, conversation, encrypted_secret, revoked_token, server_session)
- **storage/stores/**: SettingsStore (Org->Team->User resolution), SecretsStore (AES-256-GCM), ConversationStore (soft delete)
- **storage/services/**: user_service (upsert on login), token_cache_service, api_key_service (HMAC-SHA256), token_revocation_service
- **storage/encrypt_utils.py**: AES-256-GCM field encryption (HKDF from `APOLLOSAI_ENCRYPTION_KEY` + `DATABASE_URL` salt)
- **storage/database.py**: Async SQLAlchemy engine (auto-converts `postgres://` to `postgresql+asyncpg://`)
- **migrations/**: 2 Alembic versions (initial + Phase 2 schema), separate config at `apollosai/alembic.ini`
- **bootstrap.py**: Sets `OPENHANDS_CONFIG_CLS` if not overridden

## Key Patterns
- Registry (agents), Pub-Sub (events), Factory (storage/runtime), Strategy (condensers)
- Service Extension (enterprise overrides), Query/Mutation (frontend data)
- Type Guards (event discrimination), Mixin (LLM retry/debug)
- Env Var Getters (apollosai auth — prevents import-time caching)
- V0/V1 Bridge (EntraIDUserContextInjector wraps V0 auth into V1 UserContext)
- RBAC (rank-based roles: owner(0) > admin(1) > manager(2) > member(3))
- Settings Resolution (Org defaults -> Team overrides -> User overrides via TeamMembership)

# Server Architecture

## V0 Server (openhands/server/) — DEPRECATED, removal April 2026
WebSocket-based FastAPI server for agent task execution.

### Components
1. **listen.py** — Main FastAPI app, CORS, WebSocket handling, API endpoints, static file serving
2. **session/session.py** — WebSocket session management, event dispatch between client and agent
3. **session/agent_session.py** — Agent lifecycle (runtime, controller, security analyzer, event stream)
4. **conversation_manager.py** — Multi-session management, routing, cleanup of inactive sessions

### Server Lifecycle
1. FastAPI init → CORS + static files → ConversationManager init
2. Client connects via WebSocket → Session created/restarted
3. Client sends init request → Agent + Runtime + Controller configured
4. Session manages EventStream bidirectionally (client ↔ agent)
5. ConversationManager periodically cleans inactive sessions

### WebSocket API Schema

#### Actions (client → server)
- `initialize` — {model, directory, agent_cls}
- `start` — {task}
- `read` — {path}
- `write` — {path, content}
- `run` — {command}
- `browse` — {url}
- `think` — {thought}
- `finish` — task complete signal

#### Observations (server → client)
- `read` — {path} + file content
- `browse` — {url} + HTML content
- `run` — {command, exit_code} + output
- `chat` — user message

### Server Environment Variables
- `LLM_API_KEY` — API key (e.g., Anthropic)
- `LLM_MODEL` — Default model (e.g., claude-3-5-sonnet-20241022)
- `SANDBOX_VOLUMES` — Mount paths (host:container:mode)

### Server Start
```bash
uvicorn openhands.server.listen:app --reload --port 3000
```
Test with websocat: `websocat ws://127.0.0.1:3000/ws`

## V1 Server (openhands/app_server/) — NEW ARCHITECTURE
- Uses Software Agent SDK
- Routes at `/api/v1/`
- Feature-flagged via `settings?.v1_enabled`
- Both V0 and V1 coexist during transition

## ApollosAI Enterprise Server (apollosai/)

### Components (Phase 1/1.5 + Phase 2)

**Server core:**
1. **server/config.py** — `ApollosAIServerConfig` extends `ServerConfig` with `app_mode=AppMode.SAAS`, `enable_v1=True`
2. **server/lifespan.py** — `ApollosAILifespanService`: async engine init, session maker singleton, skips OpenHands migrations
3. **server/db_session.py** — `ApollosAIDbSessionInjector`: V1 `Injector[AsyncSession]` for DI
4. **server/deps.py** — FastAPI `Depends(get_db_session)` for route-level DB access
5. **server/rate_limit.py** — `slowapi` limiter (Redis backend if `REDIS_URL` set)
6. **server/middleware/db_session_middleware.py** — DB-backed server-side sessions
7. **app_server.py** — Entry point (mounts auth, org, team, API key routes + exception handlers)
8. **bootstrap.py** — Sets `OPENHANDS_CONFIG_CLS` if not overridden

**Auth:**
9. **server/auth/entraid_auth.py** — `EntraIDUserAuth`: JWT cookie + Bearer token + API key validation
10. **server/auth/user_context.py** — `EntraIDUserContextInjector`: V0->V1 bridge
11. **server/auth/jwt_utils.py** — JWT with `aud: 'apollosai'` + `jti` claims, `validate_session_token()` for revocation
12. **server/auth/msal_client.py** — MSAL `ConfidentialClientApplication` wrapper
13. **server/auth/rbac.py** — `require_auth()`, `require_role()` FastAPI dependencies, `PermissionDeniedError`
14. **server/auth/constants.py** — Env var getter functions (lazy, not import-cached)

**Routes:**
15. **server/routes/auth.py** — `/auth/login`, `/auth/callback`, `/auth/logout` (with MSAL signout)
16. **server/routes/orgs.py** — Organization CRUD with RBAC (GET/POST/PATCH/DELETE)
17. **server/routes/teams.py** — Team CRUD with RBAC
18. **server/routes/api_keys.py** — API key create/list/revoke (`sk-aai-` prefix)
19. **server/routes/models.py** — Pydantic request/response models

**Storage:**
20. **storage/models/** — 12 SQLAlchemy models (user, org, team, role, memberships, api_key, auth_token, conversation, encrypted_secret, revoked_token, server_session)
21. **storage/stores/** — SettingsStore (Org->Team->User resolution), SecretsStore (AES-256-GCM), ConversationStore (soft delete)
22. **storage/services/** — user_service, token_cache_service, api_key_service (HMAC-SHA256), token_revocation_service
23. **storage/database.py** — Async SQLAlchemy engine
24. **storage/encrypt_utils.py** — AES-256-GCM field encryption
25. **migrations/** — 2 Alembic versions (initial + Phase 2 schema)

### Auth Flow
1. User visits `/auth/login` -> redirected to Microsoft Entra ID
2. User authenticates with Entra ID -> redirected to `/auth/callback`
3. Callback receives authorization code -> exchanged for tokens via MSAL
4. Server creates JWT with `aud: 'apollosai'` claim, signed with `JWT_SECRET`
5. JWT returned to client (cookie or response body)
6. Subsequent requests include JWT -> validated by `EntraIDUserAuth` (V0) or `EntraIDUserContextInjector` (V1)

### Error Hierarchy
```
AuthError (apollosai/server/auth/auth_error.py)
  +-- NoCredentialsError    (no token provided)
  +-- InvalidTokenError     (token present but invalid/expired)
  +-- LicenseError          (valid user, invalid license)
```

### Security Rules
- JWT validation failure = hard error (never falls through to unauthenticated)
- `APOLLOSAI_ALLOW_UNAUTHENTICATED` parsed strictly: `.lower() in ('1', 'true', 'yes')`
- `JWT_SECRET` minimum 32 characters enforced at runtime
- Separate `SESSION_SECRET` for Starlette SessionMiddleware

### Environment Variables
See `docs/environment-variables.md` for the full reference (7 required, 4 optional, 1 auto-set).

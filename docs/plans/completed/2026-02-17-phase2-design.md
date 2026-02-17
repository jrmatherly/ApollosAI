# Phase 2 Design: Full Enterprise Functionality

**Date**: 2026-02-17
**Status**: Approved
**Approach**: Incremental Layers (bottom-up)
**Scope**: All 14 deferred Phase 1.5 items + RBAC + CRUD routes + frontend integration

## Phase 1/1.5 Validation Summary

All "Complete" items verified against source (~1,000+ LOC production-ready):

| Component | Status | LOC |
|-----------|--------|-----|
| Server config & entrypoint | Complete | 177 |
| Auth (EntraIDUserAuth) | Complete | 134 |
| Auth routes (login/callback/logout) | Complete | 107 |
| V1 UserContextInjector | Complete | 113 |
| Database models (8 models + Base + TimestampMixin) | Complete | 170 |
| Encryption (AES-256-GCM + HKDF) | Complete | 86 |
| JWT utilities | Complete | 79 |
| MSAL client wrapper | Complete | 77 |
| Database connectivity (async SQLAlchemy) | Complete | 43 |
| Alembic environment | Complete | 100+ |

Stubbed items confirmed:
- **SettingsStore**: `load()` returns config defaults, `store()` is `pass`
- **SecretsStore**: `load()` returns empty `Secrets()`, `store()` is `pass`
- **ConversationStore**: All 5 methods stubbed
- **RBAC middleware**: Absent (schema has role table but no enforcement)
- **Org/Team CRUD routes**: Absent (models exist, no services or routes)

Test coverage: 26 files, ~109 tests.

---

## Layer 1: DB Foundation

**Goal**: Async PostgreSQL engine available to all stores and routes via DI.

### Components

1. **`apollosai/server/db_session.py`** (new)
   - Custom `DbSessionInjector` creating async sessions from ApollosAI engine
   - Follows V1 injector pattern from `openhands/app_server/services/injector.py`
   - Caches session factory on `InjectorState`

2. **`apollosai/server/lifespan.py`** (modify)
   - Initialize async engine on startup via `create_async_engine_from_url()`
   - Store engine + session factory on app state
   - Dispose engine on shutdown

3. **Clean up empty migration**
   - Delete `bd818a71a520_initial_schema.py` (empty placeholder)
   - Real schema lives in `faeef06e7fea`

### Tests
- Engine init/dispose in lifespan
- Session factory creation
- Injector provides working async session

---

## Layer 2: Store Implementations

**Goal**: Replace 3 stub stores with real PostgreSQL-backed implementations.

### SettingsStore

**Resolution chain**: Org defaults → Team overrides → User overrides

`load()` flow:
1. Get user's `current_org_id` and `current_team_id` from User record
2. Load org-level LLM defaults from Organization table
3. Overlay team-level overrides from Team table
4. Overlay user-level overrides from TeamMembership table
5. Merge into Settings object, return

`store()` flow:
1. Determine tier (org/team/user) based on caller context
2. Upsert the appropriate record with settings delta

Mirrors `enterprise/storage/saas_settings_store.py` but adds Team tier.

### SecretsStore

`load()` flow:
1. Query secrets for `user_id` + `current_org_id`
2. Decrypt values using `encrypt_utils.decrypt_value()` with AAD = `f"{user_id}:{org_id}"`
3. Return Secrets object

`store()` flow:
1. Encrypt each secret value with `encrypt_utils.encrypt_value()` + AAD
2. Upsert encrypted blobs to DB

Requires new `encrypted_secret` table.

### ConversationStore

| Method | Implementation |
|--------|---------------|
| `save_metadata` | INSERT with user_id + org_id ownership |
| `get_metadata` | SELECT with access validation |
| `delete_metadata` | Soft delete (set `deleted_at`) |
| `exists` | SELECT EXISTS with access check |
| `search` | Paginated query filtered by user_id + org_id |

Requires new `conversation` table.

### New Alembic Migration

One migration for Phase 2 schema additions:
- `encrypted_secret` table (user_id, org_id, key, encrypted_value, nonce, aad)
- `conversation` table (id, user_id, org_id, title, metadata_json, created_at, updated_at, deleted_at)

### Tests
- Each store method tested with async SQLAlchemy
- Enterprise test patterns as reference

---

## Layer 3: Auth Completion

**Goal**: Connect auth flow to database.

### User Upsert on First Login

**Where**: `apollosai/server/routes/auth.py` callback handler

1. After MSAL token exchange, extract `oid`, `email`, `name` from `id_token_claims`
2. Upsert User: `INSERT ... ON CONFLICT (entra_oid) DO UPDATE SET email=..., updated_at=now()`
3. If first login, auto-create default Organization + OrgMembership with `owner` role
4. Set `user.current_org_id` to default org
5. Use DB `user.id` (UUID) as `sub` claim in JWT

### Token Cache Persistence

1. On login, serialize MSAL `SerializableTokenCache` to JSON
2. Encrypt with `encrypt_utils.encrypt_value()` (AAD = user_id)
3. Store in `auth_token` table (model already exists)
4. On `get_instance()`, load + decrypt cache for `acquire_token_silent()`

### API Key Authentication

Auth flow addition in `get_instance()` (before JWT cookie check):
1. Check `Authorization: Bearer sk-aai-...` header
2. Lookup ApiKey by prefix, hash key with stored salt, compare to `key_hash`
3. If match, load associated User record

New routes (`apollosai/server/routes/api_keys.py`):

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/keys` | POST | Create key (returns plaintext once) |
| `/api/keys` | GET | List keys (prefix + name only) |
| `/api/keys/{key_id}` | DELETE | Revoke key |

### Tests
- User upsert + default org creation
- Token cache round-trip
- API key create/verify/revoke
- API key auth in `get_instance()`

---

## Layer 4: RBAC + Management Routes

**Goal**: Role-based access control on all routes + Org/Team/Membership CRUD.

### RBAC Dependencies

**New file**: `apollosai/server/auth/rbac.py`

FastAPI dependency decorators:
- `require_auth` — Validates JWT, returns `AuthedUser` (user_id + org_id + role)
- `require_role(min_role)` — Checks OrgMembership role rank
- `require_org_member(org_id)` — Validates org membership
- `require_team_member(team_id)` — Validates team membership

Role hierarchy (existing `role.rank` column):

| Role | Rank | Permissions |
|------|------|------------|
| owner | 0 | Everything + delete org + transfer ownership |
| admin | 1 | Manage members, settings, teams |
| manager | 2 | Manage team members, team settings |
| member | 3 | Use platform, view org/team resources |

### Organization Routes (`apollosai/server/routes/orgs.py`)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/orgs` | GET | `require_auth` | List user's orgs |
| `/api/orgs` | POST | `require_auth` | Create org (user becomes owner) |
| `/api/orgs/{id}` | GET | `require_org_member` | Get org details |
| `/api/orgs/{id}` | PATCH | `require_role('admin')` | Update org |
| `/api/orgs/{id}` | DELETE | `require_role('owner')` | Delete org |
| `/api/orgs/{id}/members` | GET | `require_org_member` | List members |
| `/api/orgs/{id}/members` | POST | `require_role('admin')` | Invite member |
| `/api/orgs/{id}/members/{uid}` | PATCH | `require_role('admin')` | Change role |
| `/api/orgs/{id}/members/{uid}` | DELETE | `require_role('admin')` | Remove member |

### Team Routes (`apollosai/server/routes/teams.py`)

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/orgs/{oid}/teams` | GET | `require_org_member` | List teams |
| `/api/orgs/{oid}/teams` | POST | `require_role('admin')` | Create team |
| `/api/teams/{id}` | GET | `require_team_member` | Get team |
| `/api/teams/{id}` | PATCH | `require_role('manager')` | Update team |
| `/api/teams/{id}` | DELETE | `require_role('admin')` | Delete team |
| `/api/teams/{id}/members` | GET | `require_team_member` | List members |
| `/api/teams/{id}/members` | POST | `require_role('manager')` | Add member |
| `/api/teams/{id}/members/{uid}` | DELETE | `require_role('manager')` | Remove member |

### Tests
- RBAC decorator tests (allow/deny for each role level)
- CRUD endpoint tests with TestClient
- Membership cascade tests

---

## Layer 5: Security Hardening

**Goal**: Tighten security posture.

### Server-Side Sessions

Replace Starlette's cookie-based sessions (4KB limit) with DB-backed store:
- New table: `server_session` (session_id TEXT PK, data JSON, expires_at TIMESTAMP)
- New middleware: `ApollosAISessionMiddleware`
- Thin cookie contains only session ID
- Session data encrypted at rest
- TTL-based expiry with cleanup

### JWT Revocation

- Add `jti` (JWT ID) claim — random UUID per token
- New table: `revoked_token` (jti TEXT PK, revoked_at TIMESTAMP, expires_at TIMESTAMP)
- On logout, add token's `jti` to revocation table
- On validation, check revocation table
- Background cleanup of expired entries

### Rate Limiting

Using `slowapi` (FastAPI-compatible):
- `/api/auth/login`: 10 req/min per IP
- `/api/auth/callback`: 10 req/min per IP
- `/api/keys`: 5 req/min per user
- Backend: in-memory (single instance) or Redis (multi-instance)

### MSAL Signout

On logout, redirect to Microsoft's signout endpoint:
```
https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri={redirect_uri}
```

### Tests
- Session round-trip (create→read→expire)
- JWT revocation (create→revoke→reject)
- Rate limit enforcement
- MSAL signout URL construction

---

## Layer 6: Frontend Integration

**Goal**: Entra ID login + org/team selection, mirroring enterprise patterns.

### Login Page

**Modify**: `frontend/src/components/features/auth/login-content.tsx`
- Add "Sign in with Microsoft" button
- Detect ApollosAI mode via `WebClientConfig`
- Button redirects to `/api/auth/login?returnTo=...`

### Auth URL & Callback

**New**: `frontend/src/utils/generate-entra-auth-url.ts`
- Returns `/api/auth/login?returnTo=${encodeURIComponent(window.location.href)}`

**Modify**: `frontend/src/hooks/use-auth-callback.ts`
- Add `LoginMethod.ENTRA_ID = 'entra_id'`

**Modify**: `frontend/src/hooks/use-auto-login.ts`
- Support `entra_id` for session recovery

### Org/Team Selector

**New**: `frontend/src/components/features/workspace/org-selector.tsx`
- Dropdown listing user's organizations from `GET /api/orgs`
- Switching orgs updates `current_org_id` via `PATCH /api/users/me`

**New**: `frontend/src/components/features/workspace/team-selector.tsx`
- Dropdown listing teams from `GET /api/orgs/{id}/teams`
- Switching teams updates `current_team_id`

### New Hooks

- `useOrganizations()` — TanStack Query for `GET /api/orgs`
- `useTeams(orgId)` — TanStack Query for `GET /api/orgs/{id}/teams`
- `useSwitchOrg()` — Mutation, invalidates settings/secrets on switch
- `useSwitchTeam()` — Mutation, invalidates settings on switch

### New API Service

`frontend/src/api/org-service/org-service.api.ts` — Typed Axios for org/team/membership endpoints.

### Integration

- Root layout: org/team context in sidebar
- Settings: org-level settings page (admin only)
- User profile: current org/team, allow switching

### Tests
- Login flow (mock MSAL redirect)
- Org/team selector rendering
- Switching orgs invalidates queries
- Auto-login with Entra ID

---

## New Files Summary

| File | Layer | Purpose |
|------|-------|---------|
| `apollosai/server/db_session.py` | L1 | DbSessionInjector |
| `apollosai/server/routes/api_keys.py` | L3 | API key CRUD |
| `apollosai/server/auth/rbac.py` | L4 | RBAC dependencies |
| `apollosai/server/routes/orgs.py` | L4 | Org + membership CRUD |
| `apollosai/server/routes/teams.py` | L4 | Team + membership CRUD |
| `apollosai/migrations/versions/XXX_phase2_schema.py` | L2 | New tables |
| `frontend/src/utils/generate-entra-auth-url.ts` | L6 | Auth URL helper |
| `frontend/src/components/features/workspace/org-selector.tsx` | L6 | Org picker |
| `frontend/src/components/features/workspace/team-selector.tsx` | L6 | Team picker |
| `frontend/src/api/org-service/org-service.api.ts` | L6 | Org API service |
| `frontend/src/hooks/query/use-organizations.ts` | L6 | Org query hook |
| `frontend/src/hooks/query/use-teams.ts` | L6 | Team query hook |
| `frontend/src/hooks/mutation/use-switch-org.ts` | L6 | Org switch mutation |
| `frontend/src/hooks/mutation/use-switch-team.ts` | L6 | Team switch mutation |

## Modified Files Summary

| File | Layer | Changes |
|------|-------|---------|
| `apollosai/server/lifespan.py` | L1 | Engine init/dispose |
| `apollosai/storage/stores/settings_store.py` | L2 | Full implementation |
| `apollosai/storage/stores/secrets_store.py` | L2 | Full implementation |
| `apollosai/storage/stores/conversation_store.py` | L2 | Full implementation |
| `apollosai/server/routes/auth.py` | L3 | User upsert on callback |
| `apollosai/server/auth/entraid_auth.py` | L3 | API key auth path |
| `apollosai/server/auth/msal_client.py` | L3 | Token cache support |
| `apollosai/server/auth/jwt_utils.py` | L5 | jti claim + revocation |
| `apollosai/app_server.py` | L4,L5 | Mount new routes, middleware |
| `frontend/src/components/features/auth/login-content.tsx` | L6 | Entra ID button |
| `frontend/src/hooks/use-auth-callback.ts` | L6 | Entra ID login method |
| `frontend/src/hooks/use-auto-login.ts` | L6 | Entra ID session recovery |
| `frontend/src/routes/root-layout.tsx` | L6 | Org/team context |

## Dependencies to Add

**Backend** (`pyproject.toml`):
- `slowapi` — Rate limiting

**Frontend** (`package.json`):
- No new dependencies expected (uses existing Axios, TanStack Query, Zustand)

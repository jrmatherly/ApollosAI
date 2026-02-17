# Phase 3C: Frontend Admin Panels + Review Remediation — Implementation Plan

**Goal:** Build env-driven branding, admin API services, TanStack Query hooks, 8 admin panels (members, integrations, MCP, audit log, settings), feature hiding, i18n support, AND address all deferred code review findings from the Phase 3 security/architecture review.

**Scope:** Tasks 19-37 | Pillar A + Review Remediation + Final | Depends on Phase 3B (Integrations)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `docs/plans/2026-02-17-phase3-implementation.md` (index)
**Design doc:** `docs/plans/2026-02-17-phase3-design.md`
**Review findings:** `.scratchpad/phase3-review-findings.md` (32 findings, 28 unique)
**Review fixes (Batch A):** `.scratchpad/2026-02-17-phase3-review-fixes.md` (C1, C2, C4, H1, H2, H3, H4, H8 — implemented separately)

**Cross-cutting review requirements (apply to ALL tasks):**
1. **Credentials must be encrypted** — all `config_json`, `webhook_secret`, tokens, API keys stored via `SecretsStore` (AES-256-GCM), never plaintext JSON/Text columns
2. **Org-scoped queries** — every database query touching org data must include `WHERE org_id = <current_user_org_id>`, derived from auth context
3. **Timing-safe comparisons** — all HMAC/secret comparisons use `hmac.compare_digest`, never `==`
4. **Git hygiene** — use `git add <specific-file>`, never `git add .` or `git add -A`
5. **Indexes required** — every new model must define indexes for its primary query patterns
6. **Webhook responses must use HTTP status codes** — return 401/403 for auth failures, 400 for bad payloads; never return 200 with error in JSON body
7. **Enum columns** — prefer `String` with application-level validation over SQLAlchemy `Enum()` for extensibility (avoids ALTER TYPE migrations)

**Existing patterns to follow:**
- Models: `apollosai/storage/models/organization.py` (TimestampMixin, Base, mapped_column)
- Stores: `apollosai/storage/stores/settings_store.py` (async session, get_instance)
- Routes: `apollosai/server/routes/orgs.py` (APIRouter, Depends, RBAC)
- Tests: `tests/unit/apollosai/conftest.py` (async_engine, async_session, TestClient)
- Migrations: `apollosai/migrations/versions/a1b2c3d4e5f6_phase2_schema.py`
- Frontend hooks: `frontend/src/hooks/query/use-organizations.ts`
- Frontend services: `frontend/src/api/org-service/org-service.api.ts`

---

## Pillar A: Frontend

### Task 19: Branding Config — Backend

**Files:**
- Modify: `openhands/app_server/web_client/web_client_models.py`
- Modify: `openhands/app_server/web_client/default_web_client_config_injector.py`
- Test: `tests/unit/apollosai/server/test_branding.py`

**Step 1: Add branding fields to WebClientConfig**

In `web_client_models.py`, add to `WebClientConfig`:
```python
app_display_name: str | None = None
app_logo_url: str | None = None
app_primary_color: str | None = None
app_favicon_url: str | None = None
```

**Step 2: Add env-based defaults to injector**

In `default_web_client_config_injector.py`:
```python
import os

app_display_name: str | None = Field(default_factory=lambda: os.environ.get('APP_DISPLAY_NAME'))
app_logo_url: str | None = Field(default_factory=lambda: os.environ.get('APP_LOGO_URL'))
app_primary_color: str | None = Field(default_factory=lambda: os.environ.get('APP_PRIMARY_COLOR'))
app_favicon_url: str | None = Field(default_factory=lambda: os.environ.get('APP_FAVICON_URL'))
```

And pass them through in `get_web_client_config()`.

**Step 3: Write test verifying env var passthrough, commit**

```bash
git add openhands/app_server/web_client/web_client_models.py openhands/app_server/web_client/default_web_client_config_injector.py tests/unit/apollosai/server/test_branding.py
git commit -m "feat(apollosai): add env-driven branding fields to WebClientConfig"
```

---

### Task 20: Branding Config — Frontend Hook

**Files:**
- Create: `frontend/src/hooks/use-branding.ts`
- Modify: `frontend/src/api/option-service/option.types.ts` (add branding fields)

**Step 1: Add branding fields to frontend types**

In `option.types.ts`, add to `WebClientConfig`:
```typescript
app_display_name?: string;
app_logo_url?: string;
app_primary_color?: string;
app_favicon_url?: string;
```

**Step 2: Write the useBranding hook**

```typescript
// frontend/src/hooks/use-branding.ts
import { useEffect } from "react";
import { useConfig } from "./query/use-config";

export const useBranding = () => {
  const { data: config } = useConfig();

  useEffect(() => {
    if (!config) return;

    // Update document title
    if (config.app_display_name) {
      document.title = config.app_display_name;
    }

    // REVIEW: Validate favicon URL is HTTPS or relative path (prevent XSS via javascript: URLs)
    if (config.app_favicon_url) {
      const url = config.app_favicon_url;
      if (url.startsWith("https://") || url.startsWith("/")) {
        const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
        if (link) link.href = url;
      }
    }

    // REVIEW: Validate primary color matches CSS color pattern (prevent CSS injection)
    // REVIEW V2: Tightened regex — removed permissive [a-zA-Z]+ branch (allowed non-CSS values)
    if (config.app_primary_color) {
      const colorPattern = /^(#[0-9a-fA-F]{3,8}|rgb\(\d{1,3},\s?\d{1,3},\s?\d{1,3}\)|hsl\(\d{1,3},\s?\d{1,3}%,\s?\d{1,3}%\))$/;
      if (colorPattern.test(config.app_primary_color)) {
        document.documentElement.style.setProperty("--brand-primary", config.app_primary_color);
      }
    }
  }, [config]);

  return {
    appName: config?.app_display_name ?? "OpenHands",
    logoUrl: config?.app_logo_url ?? null,
    primaryColor: config?.app_primary_color ?? null,
  };
};
```

**Step 3: Wire into root layout, run frontend lint + build, commit**

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/hooks/use-branding.ts frontend/src/api/option-service/option.types.ts
git commit -m "feat(apollosai): add useBranding hook with env-driven branding support"
```

---

### Task 21: Frontend Admin API Service

**Files:**
- Create: `frontend/src/api/admin-service/admin-service.api.ts`
- Create: `frontend/src/api/admin-service/admin.types.ts`
- Create: `frontend/src/api/mcp-admin-service/mcp-admin-service.api.ts`
- Create: `frontend/src/api/integration-service/integration-service.api.ts`

**Step 1: Write typed API services**

Follow the `OrgService` pattern (static methods, typed responses, openHands axios instance).

Key services:
- `AdminService`: `getAuditLogs(orgId, params)`, `getOrgMembers(orgId)`, `inviteMember(orgId, body)`, `removeMember(orgId, userId)`, `updateRole(orgId, userId, role)`
- `MCPAdminService`: `getMCPServers()`, `addMCPServer(body)`, `updateMCPServer(id, body)`, `removeMCPServer(id)`, `testMCPServer(id)`
- `IntegrationService`: `getIntegrations()`, `getIntegrationConfig(type)`, `saveIntegrationConfig(type, body)`, `testIntegration(type)`

**Step 2: Run frontend lint, commit**

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/api/admin-service/ frontend/src/api/mcp-admin-service/ frontend/src/api/integration-service/
git commit -m "feat(apollosai): add admin, MCP, and integration API services"
```

---

### Task 22: Frontend Admin Query & Mutation Hooks

**Files:**
- Create: `frontend/src/hooks/query/use-org-members.ts`
- Create: `frontend/src/hooks/query/use-audit-log.ts`
- Create: `frontend/src/hooks/query/use-integrations.ts`
- Create: `frontend/src/hooks/query/use-mcp-servers.ts`
- Create: `frontend/src/hooks/mutation/use-invite-member.ts`
- Create: `frontend/src/hooks/mutation/use-remove-member.ts`
- Create: `frontend/src/hooks/mutation/use-update-role.ts`
- Create: `frontend/src/hooks/mutation/use-save-integration-config.ts`
- Create: `frontend/src/hooks/mutation/use-add-mcp-server.ts`
- Create: `frontend/src/hooks/mutation/use-remove-mcp-server.ts`

**Step 1: Write hooks following existing patterns**

Query hooks: `useQuery({ queryKey: [...], queryFn: ServiceMethod, enabled: condition })`
Mutation hooks: `useMutation({ mutationFn: ServiceMethod, onSuccess: () => invalidateQueries(...) })`

**Step 2: Run frontend lint, commit**

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/hooks/query/ frontend/src/hooks/mutation/
git commit -m "feat(apollosai): add admin query and mutation hooks for TanStack Query"
```

---

### Task 23: Frontend Admin Route Setup

**Files:**
- Modify: `frontend/src/routes.ts`
- Create: `frontend/src/routes/admin-members.tsx`
- Create: `frontend/src/routes/admin-teams.tsx`
- Create: `frontend/src/routes/admin-integrations.tsx`
- Create: `frontend/src/routes/admin-mcp.tsx`
- Create: `frontend/src/routes/admin-audit.tsx`
- Create: `frontend/src/routes/admin-models.tsx`
- Create: `frontend/src/routes/admin-api-keys.tsx`
- Create: `frontend/src/routes/admin-alerts.tsx`
- Modify: `frontend/src/constants/settings-nav.tsx`

**Step 1: Add admin routes to routes.ts**

Inside the `settings` layout, add:
```typescript
route("admin", "routes/admin-layout.tsx", [
  index("routes/admin-members.tsx"),
  route("teams", "routes/admin-teams.tsx"),
  route("integrations", "routes/admin-integrations.tsx"),
  route("mcp", "routes/admin-mcp.tsx"),
  route("models", "routes/admin-models.tsx"),
  route("api-keys", "routes/admin-api-keys.tsx"),
  route("audit", "routes/admin-audit.tsx"),
  route("alerts", "routes/admin-alerts.tsx"),
]),
```

**Step 2: Add admin nav items to settings-nav.tsx**

Add `ADMIN_NAV_ITEMS` array with routes for each admin page.

**Step 3: Create route components** (scaffold with loading state, data fetching, basic table/list UI)

Each route component follows the pattern:
```typescript
export default function AdminMembersPage() {
  const { data: members, isLoading } = useOrgMembers(currentOrgId);
  // ... render table/list with CRUD actions
}
```

**Step 4: Run frontend lint + build, commit**

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/routes.ts frontend/src/routes/admin-*.tsx frontend/src/constants/settings-nav.tsx
git commit -m "feat(apollosai): add admin panel routes and navigation"
```

---

### Task 24: Admin Members Panel

**Files:**
- Modify: `frontend/src/routes/admin-members.tsx`
- Create: `frontend/src/components/features/admin/member-list.tsx`
- Create: `frontend/src/components/features/admin/invite-member-modal.tsx`
- Create: `frontend/src/components/features/admin/role-selector.tsx`

Implement the members admin panel:
- Table listing org members with name, email, role, joined date
- Invite member modal (email + role selection)
- Role change dropdown per member
- Remove member button with confirmation
- RBAC: Only show for admin/owner roles

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/routes/admin-members.tsx frontend/src/components/features/admin/
git commit -m "feat(apollosai): add admin members panel with invite, role change, remove"
```

---

### Task 25: Admin Integrations Panel

**Files:**
- Modify: `frontend/src/routes/admin-integrations.tsx`
- Create: `frontend/src/components/features/admin/integration-card.tsx`
- Create: `frontend/src/components/features/admin/integration-config-modal.tsx`

Implement the integrations admin panel:
- Card grid showing each integration (GitHub, Jira, Slack, Bitbucket, Microsoft 365)
- Enable/disable toggle per integration
- Configure button -> modal with integration-specific fields (API keys, webhook URLs, etc.)
- Test connection button
- Status indicator (connected/disconnected/error)

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/routes/admin-integrations.tsx frontend/src/components/features/admin/integration-*.tsx
git commit -m "feat(apollosai): add admin integrations panel with config and status"
```

---

### Task 26: Admin MCP Panel

**Files:**
- Modify: `frontend/src/routes/admin-mcp.tsx`
- Create: `frontend/src/components/features/admin/mcp-server-card.tsx`
- Create: `frontend/src/components/features/admin/add-mcp-server-modal.tsx`

Implement the MCP admin panel:
- List of org + user MCP servers with name, type, status
- "Add MCP Server" button -> modal (name, type dropdown [stdio/sse/shttp], config fields)
- For stdio: command, args, env vars
- For sse/shttp: URL, API key
- Test connectivity button
- Enable/disable toggle
- Delete button

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/routes/admin-mcp.tsx frontend/src/components/features/admin/mcp-*.tsx frontend/src/components/features/admin/add-mcp-*.tsx
git commit -m "feat(apollosai): add admin MCP panel with BYOMCP management"
```

---

### Task 27: Admin Audit Log Viewer

**Files:**
- Modify: `frontend/src/routes/admin-audit.tsx`
- Create: `frontend/src/components/features/admin/audit-log-table.tsx`

**Prerequisite:** Task 32 (audit pagination backend) must be completed first so the frontend can consume the structured `{items, total, limit, offset}` response. If Task 32 is not yet done, scaffold the frontend assuming the paginated response shape and add a `TODO(task-32)` comment.

**Review finding addressed:** M8 (audit pagination lacks total count) — frontend must consume the paginated response from Task 32's backend changes.

Implement the audit log viewer:
- Paginated table with columns: timestamp, actor, action, resource, details
- **Pagination controls:** page forward/back, page size selector (10/25/50/100), total count display
- Filter by action type dropdown
- Filter by date range
- Auto-refresh toggle
- Click row to expand details JSON

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/routes/admin-audit.tsx frontend/src/components/features/admin/audit-*.tsx
git commit -m "feat(apollosai): add admin audit log viewer with filtering and pagination"
```

---

### Task 28: Settings Resolution UI

**Files:**
- Create: `frontend/src/components/features/settings/settings-provenance.tsx`
- Modify: existing settings inputs to show provenance indicators

Implement settings provenance indicators:
- Component: `SettingsProvenance` — shows "Set at org level" / "Overridden by team" / "Personal override" badge
- Integrate into LLM settings, app settings, and MCP settings pages
- Color-coded: org = blue, team = green, personal = purple

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/components/features/settings/settings-provenance.tsx
git commit -m "feat(apollosai): add settings provenance indicators (org/team/user tiers)"
```

---

### Task 29: Feature Hiding

**Files:**
- Modify: `frontend/src/constants/settings-nav.tsx`
- Modify: `frontend/src/routes.ts` (conditional routes)
- Modify: `frontend/src/components/features/settings/settings-navigation.tsx`

Implement app_mode-based feature hiding:
- Add `APOLLOSAI_NAV_ITEMS` to settings-nav.tsx (excludes billing, experiments, waitlist)
- Update `useSettingsNavItems()` to return `APOLLOSAI_NAV_ITEMS` when `app_mode === 'saas'` and ApollosAI is detected
- Hide reCAPTCHA components in login when `recaptcha_site_key` is null
- Conditionally render admin section only for admin/owner roles

```bash
cd frontend && npm run lint:fix && npm run build
git add frontend/src/constants/settings-nav.tsx frontend/src/routes.ts frontend/src/components/features/settings/
git commit -m "feat(apollosai): hide billing, experiments, reCAPTCHA for ApollosAI mode"
```

---

### Task 30: Wire All Routes + Final Integration

**Files:**
- Modify: `apollosai/app_server.py` (mount all new routes + CORS restriction)
- Modify: `apollosai/server/config.py` (add MCP config class override)
- Modify: `apollosai/server/routes/integrations.py` (generic error messages)

**Review findings addressed:**
- M4 (CORS allows wildcard methods and headers)
- L1 (error message leaks integration type)

**Step 1: Mount all new route routers**

In the app server route registration, include:
```python
from apollosai.server.routes.health import router as health_router
from apollosai.server.routes.admin import router as admin_router
from apollosai.server.routes.integrations import router as integrations_router
from apollosai.server.routes.mcp import router as mcp_router
```

**Step 2: Restrict CORS methods and headers (M4)**

In `apollosai/app_server.py`, replace the wildcard CORS configuration:
```python
# Before (M4 finding — overly permissive):
# allow_methods=['*'], allow_headers=['*']

# After — restrict to methods and headers the API actually uses:
allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
allow_headers=['Authorization', 'Content-Type', 'X-Request-ID', 'Accept'],
```

**Step 3: Fix generic error messages (L1)**

In `apollosai/server/routes/integrations.py`, replace:
```python
# Before (leaks integration type to unauthenticated callers):
return JSONResponse(status_code=404, content={'error': f'Unknown integration: {source}'})

# After:
return JSONResponse(status_code=404, content={'error': 'Not found'})
```

**Step 4: Set MCP config class**

In `apollosai/server/config.py` or bootstrap:
```python
os.environ.setdefault('OPENHANDS_MCP_CONFIG_CLS', 'apollosai.mcp.config.ApollosAIMCPConfig')
```

**Step 5: Register all integrations explicitly (not via import side effects)**

```python
# apollosai/integrations/__init__.py
from apollosai.integrations.models import IntegrationType
from apollosai.integrations.registry import register_integration


def register_all_integrations() -> None:
    """Register all integration managers. Call during app startup."""
    from apollosai.integrations.github.manager import GitHubIntegrationManager
    from apollosai.integrations.jira.manager import JiraIntegrationManager
    from apollosai.integrations.slack.manager import SlackIntegrationManager
    from apollosai.integrations.bitbucket.manager import BitbucketIntegrationManager
    from apollosai.integrations.microsoft.manager import MicrosoftIntegrationManager

    register_integration(IntegrationType.GITHUB, GitHubIntegrationManager)
    register_integration(IntegrationType.JIRA, JiraIntegrationManager)
    register_integration(IntegrationType.SLACK, SlackIntegrationManager)
    register_integration(IntegrationType.BITBUCKET, BitbucketIntegrationManager)
    register_integration(IntegrationType.MICROSOFT, MicrosoftIntegrationManager)
```

**IMPORTANT:** Use the actual class names from the codebase (`GitHubIntegrationManager`, `JiraIntegrationManager`, etc.), NOT the stale names from the original plan (`GitHubManager`, `JiraManager`). Verify class names with `grep -r 'class.*IntegrationManager' apollosai/integrations/` before implementing.

Call `register_all_integrations()` in the app lifespan `__aenter__`, not at module import time.

**Step 6: Run full test suite, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/ -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
cd frontend && npm run lint:fix && npm run build
```

```bash
git add apollosai/app_server.py apollosai/server/config.py apollosai/integrations/__init__.py apollosai/server/routes/integrations.py
git commit -m "feat(apollosai): wire all Phase 3 routes, restrict CORS, fix error messages"
```

---

## Review Remediation (Tasks 31-35)

These tasks address the 19 deferred findings from the Phase 3 code review that were NOT covered by the must-fix/should-fix batch (`.scratchpad/2026-02-17-phase3-review-fixes.md`).

### Task 31: MCP Config Cache Safety (H6 + L5)

**Review findings addressed:**
- H6 (MCP config cache not thread/async-safe)
- L5 (staticmethod accesses class state)

**Files:**
- Modify: `apollosai/mcp/config.py`
- Modify: `tests/unit/apollosai/mcp/test_config.py`

**Step 1: Write failing tests**

```python
# Test concurrent access doesn't corrupt cache
async def test_concurrent_cache_access():
    """H6: Verify cache handles concurrent async reads without corruption."""
    import asyncio
    tasks = [ApollosAIMCPConfig.get_config(session, org_id) for _ in range(20)]
    results = await asyncio.gather(*tasks)
    assert all(r is not None for r in results)

# Test cache respects TTL
def test_cache_ttl_expiry():
    """H6: Verify stale entries are evicted after TTL."""
    # Populate cache, advance time, verify re-fetch from DB
    pass

# Test classmethod access pattern
def test_get_cached_uses_cls_parameter():
    """L5: Verify _get_cached is a classmethod, not staticmethod."""
    assert isinstance(
        ApollosAIMCPConfig.__dict__['_get_cached'],
        classmethod
    )
```

**Step 2: Replace manual dict cache with cachetools.TTLCache**

In `apollosai/mcp/config.py`:
```python
import asyncio
from cachetools import TTLCache

class ApollosAIMCPConfig:
    _cache: TTLCache = TTLCache(maxsize=128, ttl=300)
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod  # L5: was @staticmethod
    async def _get_cached(cls, session, org_id: str) -> dict | None:
        cache_key = f'mcp_config:{org_id}'
        if cache_key in cls._cache:
            return cls._cache[cache_key]

        async with cls._lock:
            # Double-check after acquiring lock
            if cache_key in cls._cache:
                return cls._cache[cache_key]
            config = await cls._fetch_from_db(session, org_id)
            if config is not None:
                cls._cache[cache_key] = config
            return config
```

**Step 3: Run tests, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/mcp/test_config.py -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
git add apollosai/mcp/config.py tests/unit/apollosai/mcp/test_config.py
git commit -m "fix(apollosai): make MCP config cache async-safe with TTLCache and classmethod"
```

---

### Task 32: Audit Pagination Backend (M8)

**Review finding addressed:** M8 (audit pagination lacks total count, deep pagination degrades)

**Files:**
- Modify: `apollosai/server/routes/admin.py`
- Modify: `apollosai/storage/stores/audit_log_store.py` (if exists) or inline in route
- Modify: `tests/unit/apollosai/server/routes/test_admin.py`

**Step 1: Write failing tests**

```python
async def test_audit_log_returns_paginated_response():
    """M8: Response must include items, total, limit, offset."""
    response = client.get('/api/admin/audit-log?limit=10&offset=0')
    assert response.status_code == 200
    data = response.json()
    assert 'items' in data
    assert 'total' in data
    assert 'limit' in data
    assert 'offset' in data
    assert isinstance(data['total'], int)
    assert data['limit'] == 10
    assert data['offset'] == 0

async def test_audit_log_pagination_offset():
    """M8: Offset correctly skips records."""
    # Insert 15 test records, request offset=10, limit=10
    # Verify only 5 items returned, total=15
    pass
```

**Step 2: Add count query and structured response**

In `apollosai/server/routes/admin.py`:
```python
from sqlalchemy import func, select

@router.get('/audit-log')
async def get_audit_log(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=25, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    # Optional filters:
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
):
    # Count query (single scalar, fast with proper indexes)
    count_stmt = select(func.count()).select_from(AuditLog)
    # Apply same filters to count
    if action:
        count_stmt = count_stmt.where(AuditLog.action == action)
    if actor_id:
        count_stmt = count_stmt.where(AuditLog.actor_id == actor_id)
    total = (await session.execute(count_stmt)).scalar_one()

    # Data query
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    stmt = stmt.offset(offset).limit(limit)
    items = (await session.execute(stmt)).scalars().all()

    return {
        'items': [item.to_dict() for item in items],
        'total': total,
        'limit': limit,
        'offset': offset,
    }
```

**Step 3: Run tests, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/server/routes/test_admin.py -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
git add apollosai/server/routes/admin.py tests/unit/apollosai/server/routes/test_admin.py
git commit -m "fix(apollosai): add structured pagination with total count to audit log endpoint"
```

---

### Task 33: Service Client Refactor (H5 + M3 + H7 + H9)

**Review findings addressed:**
- H5 (httpx clients created per-request — TCP+TLS overhead)
- M3 (SSRF risk — URL path components from webhook payloads not validated)
- H7 (unused dependencies: slack-sdk, msgraph-sdk not wired)
- H9 (views.py files are dead code — not wired into parse_event)

**Files:**
- Modify: All 5 `service.py` files in `apollosai/integrations/*/`
- Modify: All 5 `views.py` files in `apollosai/integrations/*/`
- Modify: All 5 `manager.py` files (wire `parse_event` to use views)
- Modify: `apollosai/integrations/base.py` (shared client mixin)
- Create: `tests/unit/apollosai/integrations/test_input_validation.py`

**Step 1: Create shared httpx client mixin**

```python
# apollosai/integrations/base.py (add to existing)
class IntegrationServiceMixin:
    """Provides a shared httpx.AsyncClient with connection pooling."""

    _client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
```

**Step 2: Add URL path validation (M3)**

```python
# apollosai/integrations/base.py (add validation helpers)
import re

_REPO_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$')
_JIRA_KEY_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]+-\d+$')
_SLUG_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')


def validate_repo_path(repo: str) -> str:
    """Validate GitHub/Bitbucket repo path (owner/name)."""
    if not _REPO_PATTERN.match(repo):
        raise ValueError(f'Invalid repository path: {repo}')
    return repo


def validate_jira_key(key: str) -> str:
    """Validate Jira issue key (PROJECT-123)."""
    if not _JIRA_KEY_PATTERN.match(key):
        raise ValueError(f'Invalid Jira issue key: {key}')
    return key


def validate_slug(slug: str) -> str:
    """Validate URL slug component."""
    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f'Invalid slug: {slug}')
    return slug
```

**Step 3: Refactor service files to use shared client and validation**

Update each service.py to:
1. Inherit from `IntegrationServiceMixin` instead of creating clients per-method
2. Call validation helpers before constructing URLs
3. For Slack: evaluate whether to switch from raw httpx to `slack_sdk.web.async_client.AsyncWebClient` (H7). If `slack_sdk` patterns are complex, defer to Phase 4 with explicit TODO.
4. For Microsoft: evaluate `msgraph-sdk` adoption similarly.

**Step 4: Wire views.py into parse_event (H9)**

Each manager's `parse_event()` method should use the corresponding `views.py` Pydantic models for type-safe payload parsing:
```python
# Example: apollosai/integrations/github/manager.py
from apollosai.integrations.github.views import GitHubWebhookPayload

def parse_event(self, body: dict) -> IntegrationEvent:
    payload = GitHubWebhookPayload.model_validate(body)
    return IntegrationEvent(
        source=IntegrationType.GITHUB,
        event_type=payload.action,
        external_id=str(payload.id),
        # ... map from typed payload
    )
```

**Step 5: Write input validation tests**

```python
def test_validate_repo_path_accepts_valid():
    assert validate_repo_path('owner/repo') == 'owner/repo'

def test_validate_repo_path_rejects_traversal():
    with pytest.raises(ValueError):
        validate_repo_path('../../../etc/passwd')

def test_validate_jira_key_accepts_valid():
    assert validate_jira_key('PROJ-123') == 'PROJ-123'

def test_validate_jira_key_rejects_invalid():
    with pytest.raises(ValueError):
        validate_jira_key('not-a-key')
```

**Step 6: Run tests, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/integrations/ -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
git add apollosai/integrations/ tests/unit/apollosai/integrations/test_input_validation.py
git commit -m "refactor(apollosai): shared httpx client, input validation, wire views into parse_event"
```

---

### Task 34: Replay Protection + Payload Safety (M1 + M5)

**Review findings addressed:**
- M1 (no replay protection on GitHub/Jira/Bitbucket/Microsoft webhooks)
- M5 (raw_payload in IntegrationEvent contains full webhook body)

**Files:**
- Modify: `apollosai/integrations/base.py` (add replay protection to base)
- Modify: `apollosai/integrations/models.py` (strip sensitive fields from raw_payload)
- Create: `tests/unit/apollosai/integrations/test_replay_protection.py`

**Step 1: Add external_id-based dedup to base manager**

```python
# apollosai/integrations/base.py
from collections import OrderedDict

class ApollosAIIntegrationManager(ABC):
    _seen_events: OrderedDict = OrderedDict()
    _max_seen: int = 10000

    def _check_replay(self, external_id: str) -> bool:
        """Return True if this event was already processed (replay detected)."""
        if external_id in self._seen_events:
            return True
        self._seen_events[external_id] = True
        # Evict oldest entries when cache exceeds max
        while len(self._seen_events) > self._max_seen:
            self._seen_events.popitem(last=False)
        return False
```

For GitHub specifically, add timestamp-based rejection using `X-GitHub-Delivery` header timestamp if available (5 minute window, matching Slack's pattern).

**Step 2: Strip sensitive fields from raw_payload (M5)**

In `apollosai/integrations/models.py`, add a sanitization method:
```python
_SENSITIVE_KEYS = {'token', 'secret', 'password', 'authorization', 'api_key', 'access_token'}

@classmethod
def _sanitize_payload(cls, payload: dict) -> dict:
    """Strip potentially sensitive fields from webhook payload before storage."""
    return {
        k: (cls._sanitize_payload(v) if isinstance(v, dict) else '[REDACTED]' if k.lower() in cls._SENSITIVE_KEYS else v)
        for k, v in payload.items()
    }
```

Apply in `IntegrationEvent` construction or in the `from_webhook()` factory if one exists.

**Step 3: Write tests, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/integrations/test_replay_protection.py -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
git add apollosai/integrations/base.py apollosai/integrations/models.py tests/unit/apollosai/integrations/test_replay_protection.py
git commit -m "fix(apollosai): add replay protection and sanitize webhook payloads"
```

---

### Task 35: Resolve Encryption TODOs (Cross-cutting #1)

**Review finding addressed:** C3 (MCP config stored as plaintext in `config_encrypted` column)

**Files:**
- Modify: `apollosai/server/routes/mcp.py` (encrypt on write, decrypt on read)
- Modify: `apollosai/mcp/config.py` (decrypt on read)
- Modify: `apollosai/storage/encrypt_utils.py` (if interface changes needed)
- Modify: `tests/unit/apollosai/server/routes/test_mcp.py`

**Step 1: Write failing tests**

```python
async def test_mcp_config_is_encrypted_at_rest(async_session):
    """C3: config_encrypted column must contain encrypted bytes, not plaintext JSON."""
    # Create an MCP config via the route
    response = client.post('/api/mcp-servers', json={'name': 'test', 'config_json': {'key': 'value'}})
    assert response.status_code == 200

    # Read raw from DB — should NOT be valid JSON
    from apollosai.storage.models.user_mcp_server import UserMCPServer
    row = (await async_session.execute(select(UserMCPServer))).scalar_one()
    import json
    with pytest.raises(json.JSONDecodeError):
        json.loads(row.config_encrypted)

async def test_mcp_config_round_trips_through_encryption():
    """C3: Config can be written encrypted and read back decrypted."""
    config = {'command': 'npx', 'args': ['-y', 'some-server']}
    response = client.post('/api/mcp-servers', json={'name': 'test', 'config_json': config})
    assert response.status_code == 200

    response = client.get(f'/api/mcp-servers/{response.json()["id"]}')
    assert response.json()['config_json'] == config
```

**Step 2: Wire encryption using existing encrypt_utils.py**

In `apollosai/server/routes/mcp.py`:
```python
from apollosai.storage.encrypt_utils import encrypt_value, decrypt_value

# On create/update:
encrypted = encrypt_value(json.dumps(body.config_json).encode())
server.config_encrypted = encrypted

# On read:
decrypted = decrypt_value(server.config_encrypted)
config_json = json.loads(decrypted)
```

**Note:** The encryption infrastructure (AES-256-GCM with HKDF) already exists in `apollosai/storage/encrypt_utils.py`. This task just wires it into the MCP routes.

**Step 3: Run tests, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/server/routes/test_mcp.py -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
git add apollosai/server/routes/mcp.py apollosai/mcp/config.py tests/unit/apollosai/server/routes/test_mcp.py
git commit -m "fix(apollosai): encrypt MCP config at rest using AES-256-GCM (C3)"
```

---

## Final

### Task 36: i18n Keys

**Files:**
- Modify: `frontend/src/i18n/` translation files

**Step 1: Add all new i18n keys**

Keys needed for admin panels, integration names, MCP labels, audit actions, branding.

Run: `cd frontend && npm run make-i18n`

**Step 2: Commit**

```bash
git add frontend/src/i18n/
git commit -m "chore: add Phase 3 i18n keys for admin panels, integrations, MCP"
```

---

### Task 37: Final Pre-Commit + Full Test Run + Cleanup

**Review findings addressed in this cleanup pass:**
- L4 (SourceType alias creates naming confusion)
- L7 (MonitoringListener tests only verify "does not raise")
- C2 test gap (Jira, Bitbucket, Slack managers lack fail-closed regression tests)

**Step 1: Add missing fail-closed tests for C2 (Jira, Bitbucket, Slack)**

The PR #7 fix for C2 (fail-closed webhook validation) only added regression tests for GitHub and Microsoft managers. Jira, Bitbucket, and Slack managers have correct fail-closed code but no tests protecting against regression. Create `tests/unit/apollosai/integrations/test_fail_closed.py` with parametrized tests covering all 5 managers:

```python
"""Parametrized fail-closed tests for all integration managers (C2 regression protection)."""

import json
import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.bitbucket.manager import BitbucketIntegrationManager
from apollosai.integrations.github.manager import GitHubIntegrationManager
from apollosai.integrations.jira.manager import JiraIntegrationManager
from apollosai.integrations.microsoft.manager import MicrosoftIntegrationManager
from apollosai.integrations.slack.manager import SlackIntegrationManager

MANAGERS = [
    GitHubIntegrationManager,
    JiraIntegrationManager,
    SlackIntegrationManager,
    BitbucketIntegrationManager,
    MicrosoftIntegrationManager,
]


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


@pytest.mark.parametrize('manager_cls', MANAGERS, ids=lambda c: c.__name__)
def test_no_secret_rejects_webhook(manager_cls, monkeypatch):
    """Managers without credentials must reject webhooks (fail closed)."""
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', raising=False)
    manager = manager_cls()
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=json.dumps({'type': 'event_callback'}).encode(),
        headers={'content-type': 'application/json'},
    )
    assert resp.status_code == 401, (
        f'{manager_cls.__name__} should reject when no secret configured'
    )


@pytest.mark.parametrize('manager_cls', MANAGERS, ids=lambda c: c.__name__)
def test_allow_unsigned_env_permits_webhook(manager_cls, monkeypatch):
    """APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true allows unsigned webhooks."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', 'true')
    manager = manager_cls()
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=json.dumps({
            'type': 'event_callback',
            'event': {'type': 'app_mention', 'text': 'hi', 'channel': 'C1', 'ts': '1'},
        }).encode(),
        headers={'content-type': 'application/json'},
    )
    assert resp.status_code != 401, (
        f'{manager_cls.__name__} should allow when APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true'
    )
```

**Step 2: Remove SourceType alias (L4)**

In `apollosai/integrations/models.py`, remove:
```python
# Remove this alias:
SourceType = IntegrationType
```

Then find and update all references:
```bash
grep -rn 'SourceType' apollosai/ tests/
```
Replace all `SourceType` references with `IntegrationType` throughout the codebase.

**Step 3: Improve MonitoringListener tests (L7)**

In `tests/unit/apollosai/monitoring/test_listener.py`, replace "does not raise" assertions with specific log verification:
```python
def test_monitoring_listener_logs_event(caplog):
    """L7: Verify MonitoringListener logs with expected structured data."""
    import logging
    with caplog.at_level(logging.INFO):
        listener.on_event(test_event)
    assert len(caplog.records) == 1
    assert caplog.records[0].msg == 'Event processed'
    assert caplog.records[0].__dict__['extra']['event_type'] == 'test_type'
```

**Step 4: Run all backend tests**

```bash
poetry run pytest tests/unit/apollosai/ -v --tb=short
```

**Step 5: Run all frontend tests**

```bash
cd frontend && npm run test
```

**Step 6: Run pre-commit on all files**

```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
cd frontend && npm run lint:fix && npm run build
```

**Step 7: Fix any issues, commit**

```bash
# REVIEW: Never use `git add -A` — stage specific files per project convention
git add <specific-changed-files>
git commit -m "chore: Phase 3C lint fixes, SourceType cleanup, test improvements"
```

---

## Review Findings Tracking

This section tracks the disposition of all 32 findings from `.scratchpad/phase3-review-findings.md`.

### Addressed by Must-Fix/Should-Fix Batch (9 findings)
Implemented in `.scratchpad/2026-02-17-phase3-review-fixes.md`:

| ID | Finding | Fix Task |
|----|---------|----------|
| C1 | Integration registry never populated | Fix Task 1 |
| C2 | All webhook managers bypass validation when secret is None | Fix Task 2 |
| C4 | Microsoft validationToken bypasses signature verification | Fix Task 3 |
| H1 | PermissionDeniedError not registered as exception handler | Fix Task 4 |
| H2 | Session cookie `https_only=False` by default | Fix Task 5 |
| H3 | API key routes bypass RBAC — no org membership check | Fix Task 6 |
| H4 | Slack url_verification responds before signature validation | Fix Task 7 |
| H8 | handle_webhook return type mismatch (Microsoft) | Fix Task 8 |
| C3 | MCP config stored as plaintext in `config_encrypted` column | **Also** Task 35 (encryption wiring) |

### Addressed in Phase 3C (14 findings)

| ID | Finding | Phase 3C Task |
|----|---------|---------------|
| H5 | httpx clients created per-request | Task 33 |
| H6 | MCP config cache not thread/async-safe | Task 31 |
| H7 | Unused dependencies (slack-sdk, msgraph-sdk, OTEL) | Task 33 |
| H9 | views.py files are dead code | Task 33 |
| M1 | No replay protection on webhooks | Task 34 |
| M3 | SSRF risk in integration service clients | Task 33 |
| M4 | CORS allows wildcard methods and headers | Task 30 |
| M5 | raw_payload contains full webhook body | Task 34 |
| M8 | Audit pagination lacks total count | Task 32 |
| L1 | Error message leaks integration type | Task 30 |
| L4 | SourceType alias creates naming confusion | Task 37 |
| L5 | staticmethod accesses class state | Task 31 |
| L7 | MonitoringListener tests only verify "does not raise" | Task 37 |
| C3 | MCP config encryption (cross-cutting) | Task 35 |

### Won't-Fix / Acceptable As-Is (8 findings)

| ID | Finding | Rationale |
|----|---------|-----------|
| M2 | MCP config allows arbitrary command execution | Admin approval gate exists; allowlisting is product decision, not code bug |
| M6 | Redis health probe creates new connection per call | Acceptable for health checks; redis pool sharing is optimization, not correctness |
| M7 | Slack manager double-parses webhook body | Resolved by H4 fix (signature-first rewrite eliminates double parse) |
| M9 | deps.py auto-commits on success | Common FastAPI pattern; read-only routes are lightweight; explicit commits add noise |
| M10 | Implicit re-export in app_server.py | Minor indirection; import chain is stable and well-documented |
| M11 | Migration index uses sa.text() — non-portable | PostgreSQL is the only supported DB; SQLite portability is test-only concern and handled by test fixtures |
| L2 | Rate limiter trusts X-Forwarded-For | Deployment concern — documented as requiring trusted proxy; application-level fix would be incorrect |
| L3 | OTEL uses threading.Lock in async context | Only used at startup (once); no performance impact on hot path |

### Additional Plan Concerns Identified

| Concern | Description | Resolution |
|---------|-------------|------------|
| Stale class names in Task 30 | Plan used `GitHubManager` but actual classes are `GitHubIntegrationManager`, etc. | Fixed in Task 30 |
| Phase 3B Task 14 slack_sdk gap | Plan says use slack_sdk but implementation uses raw httpx | Evaluated in Task 33 |
| Phase 3B Task 10 replay protection | Base manager has REVIEW comment about replay but never implemented | Task 34 |
| Encryption TODOs not fulfilled | `TODO(phase3c)` in mcp.py routes for SecretsStore encryption | Task 35 |
| L6 (cache eviction test) | Test duplicates production logic | Resolved by Task 31's TTLCache refactor (removes manual eviction) |
| L8 (Jira HMAC validation) | Identifier comparison vs body signature | Deferred — requires Jira Cloud API investigation |

---

## Summary

| Section | Tasks | Key Deliverables |
|---------|-------|-----------------|
| C: Monitoring | 1-8 | Audit log, health endpoints, OTEL setup, monitoring listener, migration |
| B: Integrations | 9-18 | Base manager, registry, GitHub/Jira/Slack/Bitbucket/Microsoft managers, MCP config, dependencies |
| A: Frontend | 19-30 | Branding, admin API services, hooks, 8 admin panels, settings provenance, feature hiding, route wiring |
| Review Remediation | 31-35 | MCP cache safety, audit pagination, service client refactor, replay protection, encryption |
| Final | 36-37 | i18n keys, full test suite, pre-commit, lint, SourceType cleanup, test improvements |

**Total: 37 tasks, ~70-90 files created/modified**

**Review coverage:** 9 of 32 findings addressed in PR #7, 14 planned for Phase 3C (Tasks 31-35 + amendments). 8 accepted as-is. 1 deferred (L8 Jira HMAC).

**Estimated new test count**: ~100-140 tests across backend integration/monitoring/route/validation tests

# Phase 3C: Frontend Admin Panels — Implementation Plan

**Goal:** Build env-driven branding, admin API services, TanStack Query hooks, 8 admin panels (members, integrations, MCP, audit log, settings), feature hiding, and i18n support.

**Scope:** Tasks 19-32 | Pillar A + Final | Depends on Phase 3B (Integrations)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Parent plan:** `docs/plans/2026-02-17-phase3-implementation.md` (index)
**Design doc:** `docs/plans/2026-02-17-phase3-design.md`

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
- Configure button → modal with integration-specific fields (API keys, webhook URLs, etc.)
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
- "Add MCP Server" button → modal (name, type dropdown [stdio/sse/shttp], config fields)
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

Implement the audit log viewer:
- Paginated table with columns: timestamp, actor, action, resource, details
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
- Modify: `apollosai/app_server.py` (mount all new routes)
- Modify: `apollosai/server/config.py` (add MCP config class override)

**Step 1: Mount all new route routers**

In the app server route registration, include:
```python
from apollosai.server.routes.health import router as health_router
from apollosai.server.routes.admin import router as admin_router
from apollosai.server.routes.integrations import router as integrations_router
from apollosai.server.routes.mcp import router as mcp_router
```

**Step 2: Set MCP config class**

In `apollosai/server/config.py` or bootstrap:
```python
os.environ.setdefault('OPENHANDS_MCP_CONFIG_CLS', 'apollosai.mcp.config.ApollosAIMCPConfig')
```

**Step 3: Register all integrations explicitly (not via import side effects)**

```python
# REVIEW: Use explicit registration function, not import side effects (Architecture finding)
# apollosai/integrations/__init__.py
from apollosai.integrations.models import IntegrationType
from apollosai.integrations.registry import register_integration


def register_all_integrations() -> None:
    """Register all integration managers. Call during app startup."""
    from apollosai.integrations.github.manager import GitHubManager
    from apollosai.integrations.jira.manager import JiraManager
    from apollosai.integrations.slack.manager import SlackManager
    from apollosai.integrations.bitbucket.manager import BitbucketManager
    from apollosai.integrations.microsoft.manager import MicrosoftManager

    register_integration(IntegrationType.GITHUB, GitHubManager)
    register_integration(IntegrationType.JIRA, JiraManager)
    register_integration(IntegrationType.SLACK, SlackManager)
    register_integration(IntegrationType.BITBUCKET, BitbucketManager)
    register_integration(IntegrationType.MICROSOFT, MicrosoftManager)
```

Call `register_all_integrations()` in the app lifespan `__aenter__`, not at module import time.

**Step 4: Run full test suite, pre-commit, commit**

```bash
poetry run pytest tests/unit/apollosai/ -v
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
cd frontend && npm run lint:fix && npm run build
```

```bash
git add apollosai/app_server.py apollosai/server/config.py apollosai/integrations/__init__.py
git commit -m "feat(apollosai): wire all Phase 3 routes and integration registrations"
```

---

### Task 31: i18n Keys

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

### Task 32: Final Pre-Commit + Full Test Run

**Step 1: Run all backend tests**

```bash
poetry run pytest tests/unit/apollosai/ -v --tb=short
```

**Step 2: Run all frontend tests**

```bash
cd frontend && npm run test
```

**Step 3: Run pre-commit on all files**

```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
cd frontend && npm run lint:fix && npm run build
```

**Step 4: Fix any issues, commit**

```bash
# REVIEW: Never use `git add -A` — stage specific files per project convention
git add <specific-changed-files>
git commit -m "chore: Phase 3 lint fixes and test cleanup"
```

---

## Summary

| Pillar | Tasks | Key Deliverables |
|--------|-------|-----------------|
| C: Monitoring | 1-8 | Audit log, health endpoints, OTEL setup, monitoring listener, migration |
| B: Integrations | 9-18 | Base manager, registry, GitHub/Jira/Slack/Bitbucket/Microsoft managers, MCP config, dependencies |
| A: Frontend | 19-31 | Branding, admin API services, hooks, 8 admin panels, settings provenance, feature hiding, i18n |
| Final | 32 | Full test suite, pre-commit, lint |

**Total: 32 tasks, ~60-80 files created/modified**

**Estimated new test count**: ~80-120 tests across backend integration/monitoring/route tests

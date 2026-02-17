# ApollosAI Phase 3: Comprehensive Enterprise — Design Document

> Date: 2026-02-17
> Status: Approved
> Depends on: Phase 1/1.5 (PR #1, merged), Phase 2 (PR #5, merged)

## Purpose

Phase 3 combines the remaining frontend polish, a full integration framework (GitHub, Jira, Slack, Bitbucket, Microsoft 365), per-org MCP management with "bring your own" MCP servers, OTEL-based monitoring with alerting, audit logging, and full admin panels. This is the largest phase and brings ApollosAI to feature parity for internal enterprise use.

## Architecture

### Three Pillars (build order)

```
Pillar C: Monitoring & Hardening     (foundation — built first)
    ↓ provides health endpoints, audit logging, OTEL traces, alerting
Pillar B: Integrations               (core — biggest new surface area)
    ↓ provides integration configs for admin panels
Pillar A: Frontend Polish            (UI layer — consumes everything below)
```

**Rationale**: Monitoring gives observability while building integrations. Integrations provide the data/config that admin panels need. Frontend comes last because it consumes APIs from both.

### New Directory Structure

```
apollosai/
├── integrations/                    # Pillar B
│   ├── base.py                      # ApollosAIIntegrationManager (rich base)
│   ├── models.py                    # Message, SourceType, IntegrationEvent
│   ├── registry.py                  # Integration discovery + registration
│   ├── github/
│   │   ├── manager.py               # GitHubManager
│   │   ├── service.py               # GitHub API client
│   │   └── views.py                 # Issue, PR context views
│   ├── jira/
│   │   ├── manager.py               # JiraManager
│   │   ├── service.py               # Jira Cloud API client
│   │   └── views.py                 # Issue context views
│   ├── slack/
│   │   ├── manager.py               # SlackManager
│   │   ├── service.py               # Slack API client (AsyncWebClient)
│   │   └── views.py                 # Conversation context views
│   ├── bitbucket/
│   │   ├── manager.py               # BitbucketManager
│   │   ├── service.py               # Bitbucket API client
│   │   └── views.py                 # PR/issue context views
│   └── microsoft/
│       ├── manager.py               # MicrosoftManager (Graph API)
│       ├── service.py               # Microsoft Graph client
│       ├── mcp_tools.py             # Graph operations as MCP tools
│       └── views.py                 # Document/email context views
├── mcp/                             # Per-org MCP extension
│   ├── config.py                    # ApollosAIMCPConfig
│   └── user_mcp_store.py            # BYOMCP server storage
├── monitoring/                      # Pillar C
│   ├── listener.py                  # ApollosAIMonitoringListener
│   ├── otel.py                      # OTEL tracer/meter providers
│   ├── audit.py                     # Audit log service
│   ├── alerts.py                    # Alert definitions + Slack notification
│   └── health.py                    # Health/readiness checks
├── server/
│   ├── routes/
│   │   ├── integrations.py          # Webhook + management endpoints
│   │   ├── admin.py                 # Admin panel API endpoints
│   │   ├── mcp.py                   # Per-org MCP management
│   │   └── health.py                # /ready, /health
│   └── ...existing...
├── storage/
│   ├── models/
│   │   ├── integration_config.py    # Per-org integration settings
│   │   ├── github_installation.py   # GitHub App installation
│   │   ├── slack_workspace.py       # Slack workspace + bot token
│   │   ├── jira_workspace.py        # Jira workspace + service account
│   │   ├── bitbucket_workspace.py   # Bitbucket workspace credentials
│   │   ├── microsoft_connection.py  # Microsoft 365 tenant connection
│   │   ├── integration_conversation.py  # Maps integration → conversation
│   │   ├── user_mcp_server.py       # BYOMCP server configs
│   │   └── audit_log.py             # Admin action audit trail
│   └── ...existing...
└── ...existing...
```

## Pillar C: Monitoring & Hardening

### OTEL Instrumentation

**Strategy**: Env-based OTEL configuration supporting both deployment targets.

| Target | Collector | Config |
|--------|-----------|--------|
| Docker Compose (dev) | Jaeger + Prometheus + Grafana | `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` |
| Kubernetes (prod) | OTEL Collector sidecar → backend | `OTEL_EXPORTER_OTLP_ENDPOINT` from pod env |

**Setup** (`apollosai/monitoring/otel.py`):
- Initialize `TracerProvider` and `MeterProvider` in the lifespan service
- Use standard `OTEL_EXPORTER_OTLP_ENDPOINT` env var
- Auto-instrument: FastAPI (request traces), SQLAlchemy (query spans), httpx (outbound HTTP)
- Custom spans: conversation lifecycle, integration webhook processing, auth flows

**New dependencies**: `opentelemetry-instrumentation-fastapi`, `opentelemetry-instrumentation-sqlalchemy`, `opentelemetry-instrumentation-httpx`

### Monitoring Listener

**`ApollosAIMonitoringListener`** extends the V0 `MonitoringListener` ABC:
- `on_session_event` → OTEL counter for agent errors + structured log
- `on_agent_session_start` → OTEL histogram for session duration
- `on_create_conversation` → OTEL counter for conversation creation
- Custom: `on_integration_event` → counter by integration type + org

### Health & Readiness

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `GET /health` | Liveness probe | Process running (always 200) |
| `GET /ready` | Readiness probe | DB `SELECT 1` + Redis ping (if configured) |

K8s probe-compatible JSON response format.

### Audit Logging

**`AuditLog` model**:
- `id`, `actor_id`, `action` (enum), `resource_type`, `resource_id`, `details` (JSONB), `ip_address`, `created_at`
- Actions: `member_invited`, `member_removed`, `role_changed`, `integration_configured`, `mcp_server_added`, `settings_updated`, `api_key_created`, `api_key_revoked`
- Auto-populated via decorator on admin routes
- Queryable via admin API (paginated, filterable by action/actor/date range)

### Alerting

**Architecture**: OTEL-native alerting via the collector stack, not application-level.

- **Docker Compose**: Prometheus → Alertmanager → Slack webhook
- **Kubernetes**: OTEL Collector → Prometheus/Azure Monitor → alert rules

**Application-level alert definitions** (`apollosai/monitoring/alerts.py`):
- Emit OTEL metrics with alert-worthy labels
- Key metrics: `agent.error.rate`, `auth.failure.count`, `integration.webhook.failure`, `db.pool.exhaustion`
- Slack notification for critical alerts (reuses Slack integration service)
- Config: `ALERT_SLACK_WEBHOOK_URL`, `ALERT_THRESHOLD_*` env vars

### Rate Limiting Enhancement

Phase 2 delivered per-user `slowapi` rate limiting. Phase 3 adds:
- Per-org rate limiting (shared budget across org members)
- Integration webhook rate limiting (per-integration, per-org)
- Audit log query rate limiting

## Pillar B: Integration Framework

### Rich Base Manager

**`ApollosAIIntegrationManager`** (`apollosai/integrations/base.py`) provides:

| Capability | Implementation |
|------------|---------------|
| HTTP client | `httpx.AsyncClient` with configurable retry/backoff |
| Credential store | Read/write integration tokens via `SecretsStore` (AES-256-GCM) |
| Webhook verification | HMAC-SHA256, configurable per-integration |
| Rate limiting | Per-integration, per-org via existing `slowapi` |
| OTEL tracing | Auto-creates spans for webhook processing |
| Audit logging | Auto-logs integration events |
| Conversation creation | Helper to create conversation with platform context |

**Abstract methods** each integration must implement:

```python
class ApollosAIIntegrationManager(ABC):
    async def validate_webhook(self, request: Request) -> bool: ...
    async def parse_event(self, payload: dict) -> IntegrationEvent: ...
    async def build_context(self, event: IntegrationEvent) -> ConversationContext: ...
    async def post_response(self, conversation_id: str, message: str) -> None: ...
    def get_oauth_config(self) -> OAuthConfig | None: ...
```

### Integration Implementations

#### GitHub
- **Events**: Issue labeled, PR comment, issue comment (`@openhands` mention)
- **Auth**: GitHub App installation tokens
- **Response**: Posts completion messages as issue/PR comments
- **Storage**: `GitHubInstallation` (installation_id, encrypted token)

#### Jira
- **Events**: Issue created/updated with trigger label, comment created
- **Auth**: Jira Cloud API via service account (encrypted API key)
- **Response**: Posts completion as Jira comments
- **Storage**: `JiraWorkspace` (workspace URL, encrypted API key, service account)

#### Slack
- **Events**: Slash commands, @mentions, interactive messages
- **Auth**: Bot token via OAuth flow
- **Response**: Thread-based conversation updates
- **Storage**: `SlackWorkspace` (team_id, bot_token encrypted, signing_secret)

#### Bitbucket
- **Events**: PR comment, issue comment
- **Auth**: App password or OAuth consumer
- **Response**: Posts completion as PR/issue comments
- **Storage**: `BitbucketWorkspace` (workspace_id, encrypted credentials)

#### Microsoft 365
- **Unique**: Both event integration AND MCP tool provider
- **Auth**: Existing MSAL/Entra ID tokens + additional Graph scopes (`Sites.Read.All`, `Files.ReadWrite.All`, `Mail.Read`, `Calendars.Read`)
- **Capabilities**:
  - SharePoint/OneDrive: Read/search documents, access team sites, pull file content as agent context
  - Outlook: Read emails for context, calendar awareness
  - Teams: Post conversation updates (like Slack pattern)
- **MCP tools**: Graph operations exposed as MCP tools (search documents, read files, list emails)
- **Storage**: `MicrosoftConnection` (org_id, tenant_id, scopes granted, encrypted refresh token)

### Per-Org MCP Configuration

**`ApollosAIMCPConfig`** overrides `OPENHANDS_MCP_CONFIG_CLS`:

- `create_default_mcp_server_config()` merges: global defaults + org-level servers + user "bring your own" servers
- Storage: `UserMCPServer` model (user_id, org_id, server_type, config JSON encrypted, enabled flag)

**"Bring Your Own" MCP servers**:
- Users configure custom MCP servers via admin UI (name, type, command/URL, env vars, API key)
- Configs stored encrypted in `user_mcp_server` table
- On conversation start, user's MCP servers loaded alongside org defaults
- Org admins can set MCP policies (allowlist commands, disable stdio servers, etc.)

### Integration Routes

```
POST /api/integrations/{type}/webhook    — Webhook receiver
GET  /api/integrations/{type}/config     — Get org integration config
PUT  /api/integrations/{type}/config     — Update org integration config
POST /api/integrations/{type}/test       — Test connection
GET  /api/integrations/{type}/status     — Integration health status
GET  /api/integrations                   — List all integrations + status

POST /api/mcp/servers                    — Add custom MCP server (BYOMCP)
GET  /api/mcp/servers                    — List org + user MCP servers
PUT  /api/mcp/servers/{id}               — Update MCP server config
DELETE /api/mcp/servers/{id}             — Remove MCP server
POST /api/mcp/servers/{id}/test          — Test MCP server connectivity
```

## Pillar A: Frontend Polish

### Env-Driven Branding

**Config endpoint extension** — `/api/options` response gains:
- `app_name` (env: `APP_DISPLAY_NAME`, default: "OpenHands")
- `app_logo_url` (env: `APP_LOGO_URL`, default: built-in SVG)
- `app_primary_color` (env: `APP_PRIMARY_COLOR`, default: theme color)
- `app_favicon_url` (env: `APP_FAVICON_URL`)

**Frontend**: `useBranding()` hook applies document title, logo swap, CSS custom properties, favicon.

### Full Admin Panels

**Admin routes** (`/settings/admin/*`), RBAC-gated to org owners/admins:

| Route | Purpose |
|-------|---------|
| `/settings/admin/members` | Org member management (invite, remove, role change) |
| `/settings/admin/teams` | Team CRUD, member assignment |
| `/settings/admin/roles` | Role definitions and permissions |
| `/settings/admin/integrations` | Integration configs (GitHub App, Jira workspace, Slack bot, Bitbucket, Microsoft 365) |
| `/settings/admin/mcp` | Org MCP servers + BYOMCP management |
| `/settings/admin/models` | LLM model allowlist / API key policies per org |
| `/settings/admin/api-keys` | Org API key management |
| `/settings/admin/audit` | Audit log viewer (paginated, filterable) |
| `/settings/admin/alerts` | Alert configuration and threshold management |

### Settings Resolution UI

Settings pages show effective values with provenance indicators:
- "Set at org level" / "Overridden by team" / "Personal override"
- Team admins can override org defaults for their team
- Users can override for themselves (where allowed by org policy)
- Follows existing settings pattern: form-based for config, entity-based for CRUD

### Feature Hiding

Conditionally hidden based on `app_mode` config:
- Billing/subscription UI → hidden when `app_mode !== 'saas'`
- Experiment flags → hidden
- Waitlist/invite-only UI → hidden
- reCAPTCHA → hidden (internal tool)
- Provider-specific login buttons → show only configured providers

### Frontend API Layer

**New services**:
- `AdminService` — member/team/role CRUD, integration config, audit logs
- `MCPService` — MCP server CRUD, test connectivity
- `IntegrationService` — integration status, test connections

**New hooks**:
- Query: `useOrgMembers`, `useOrgTeams`, `useOrgRoles`, `useIntegrations`, `useIntegrationConfig`, `useMCPServers`, `useAuditLog`, `useAlertConfig`
- Mutation: `useInviteMember`, `useRemoveMember`, `useUpdateRole`, `useSaveIntegrationConfig`, `useAddMCPServer`, `useRemoveMCPServer`, `useTestIntegration`, `useTestMCPServer`

## New Storage Models (Alembic migration 003)

| Model | Purpose | Key Fields |
|-------|---------|------------|
| `IntegrationConfig` | Per-org integration settings | org_id, type, enabled, config (JSONB encrypted) |
| `GitHubInstallation` | GitHub App tokens | installation_id, org_id, encrypted_token |
| `SlackWorkspace` | Slack bot credentials | team_id, org_id, bot_token (encrypted), signing_secret |
| `JiraWorkspace` | Jira connection | workspace_url, org_id, api_key (encrypted), service_account |
| `BitbucketWorkspace` | Bitbucket credentials | workspace_id, org_id, credentials (encrypted) |
| `MicrosoftConnection` | M365 tenant connection | org_id, tenant_id, scopes, refresh_token (encrypted) |
| `IntegrationConversation` | Integration → conversation map | integration_type, external_id, conversation_id, org_id |
| `UserMCPServer` | BYOMCP configs | user_id, org_id, server_type, config (encrypted), enabled |
| `AuditLog` | Admin action trail | actor_id, action, resource_type, resource_id, details (JSONB), ip_address |

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Integration architecture | Rich Base Manager | Shared HTTP, credentials, webhook verification reduces per-integration code |
| MCP extension | Override `OPENHANDS_MCP_CONFIG_CLS` | Standard extension point; merges org + user servers |
| BYOMCP security | Org-admin-configurable policies | Trust org admins; they set allowlists/restrictions for their org |
| Branding | Env-driven (not hardcoded) | Flexible for multi-tenant or white-label without code changes |
| Alerting | OTEL-native via collector | Keeps app thin; Prometheus/Alertmanager handles thresholds |
| Microsoft 365 | Dual role (events + MCP tools) | Graph API enables both webhook events and tool-based document access |
| OTEL deployment | Env-based (`OTEL_EXPORTER_OTLP_ENDPOINT`) | Standard convention; works in Docker Compose and K8s without code changes |
| Admin UI | Full panels (10 routes) | Internal enterprise tool needs self-service admin capabilities |

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Integration scope creep | High | Rich base manager reduces per-integration effort; strict adapter pattern |
| Microsoft Graph API complexity | Medium | Start with read-only scopes; expand incrementally |
| MCP server injection (BYOMCP) | High | Encrypted storage, org-level policies, validated configs |
| OTEL performance overhead | Low | Sampling rate configurable; auto-instrumentation is low-overhead |
| Admin panel feature bloat | Medium | Each admin page is independent; can defer individual pages |
| V0 deprecation (April 2026) | Medium | MonitoringListener is V0; build V1-compatible from start |

## Dependencies

**Python packages to add**:
- `opentelemetry-instrumentation-fastapi`
- `opentelemetry-instrumentation-sqlalchemy`
- `opentelemetry-instrumentation-httpx`
- `slack-sdk` (Slack AsyncWebClient)
- `atlassian-python-api` or `jira` (Jira Cloud API)
- `msgraph-sdk` (Microsoft Graph)

**Frontend packages**: None expected — existing stack (TanStack Query, Zustand, HeroUI) covers all needs.

## Clean-Room Process

Same as Phase 1/2: All code written from scratch against documented interfaces. Enterprise integration patterns studied for structure (Manager/View/Service) but implementations use different libraries, different auth providers (Entra ID vs Keycloak), and different storage patterns.

---

## Review Amendments (2026-02-17)

> Multi-dimensional review conducted across Security, Architecture, and Performance dimensions.
> Design doc: 59 findings (8 Critical, 17 High, 21 Medium, 13 Low).
> Implementation plan: 48 findings (4 Critical, 14 High, 18 Medium, 12 Low).
> Amendments below are incorporated into the design and must be followed during implementation.

### Critical: BYOMCP Command Injection (Security C1/C2)

**Problem**: Allowing users to specify arbitrary stdio commands and environment variables in BYOMCP configs creates a direct path to remote code execution.

**Amendment**:
- BYOMCP stdio servers require org-admin approval before activation (not user self-service)
- Implement command allowlist at org level (`allowed_mcp_commands` in Organization settings)
- Validate and sanitize all BYOMCP config fields before storage
- Environment variables: strip `PATH`, `LD_PRELOAD`, `PYTHONPATH`, and other injection-prone vars
- Config stored via `SecretsStore` (AES-256-GCM), never plaintext JSON
- Add `MCPPolicy` model for org-level restrictions (allowlisted commands, disable stdio toggle)

### Critical: Microsoft 365 Scope Escalation (Security C3)

**Problem**: Refresh tokens can grant broader Graph API scopes than initially authorized. `Files.ReadWrite.All` is over-permissioned for read-only document context.

**Amendment**:
- Start with read-only scopes: `Sites.Read.All`, `Files.Read.All`, `Mail.Read`, `Calendars.Read`
- Scope stored per-connection; validated on each token refresh (reject scope escalation)
- Write scopes (`Files.ReadWrite.All`) only granted via explicit admin consent flow
- Token refresh must validate returned scopes match stored `scopes_granted` field
- Add `MicrosoftConnection.scopes_granted` as explicit allowlist (not just audit)

### Critical: Webhook Authentication Policy (Security C4)

**Problem**: Webhook endpoints bypass JWT auth (signature-only), contradicting the existing "never fall through" JWT policy.

**Verification**: This is standard for all webhook receivers — GitHub, Slack, Jira all verify via HMAC, not JWT. The existing enterprise code (`enterprise/integrations/jira_dc/jira_dc_manager.py:146-148`) already uses `hmac.compare_digest` for webhook signature verification.

**Amendment**:
- Webhook endpoints are explicitly documented as signature-only (no JWT) — this is intentional and standard
- Each integration's `validate_webhook` must use timing-safe HMAC comparison (`hmac.compare_digest`)
- Add replay protection: validate `X-Request-ID` / timestamp header, reject events older than 5 minutes
- Webhook routes mounted under `/api/webhooks/` prefix for clarity (not a security fix — just organizational)
- Rate limit webhook endpoints per-integration per-org (separate from user rate limits)

### Critical: V0 MonitoringListener Deprecation (Architecture C1)

**Problem**: `MonitoringListener` ABC is V0-only with hard removal April 1, 2026. Building on it creates ~6 weeks of runway.

**Amendment**:
- `ApollosAIMonitoringListener` is a V0 adapter that delegates to a standalone `MonitoringService`
- `MonitoringService` contains all actual logic (OTEL metrics, structured logging)
- When V1 provides a monitoring extension point, swap the adapter layer only
- If V0 is removed before V1 provides an alternative, `MonitoringService` can be called directly from the lifespan service
- Track upstream V1 monitoring API: if available before Phase 3 implementation, use V1 directly

### Critical: OTEL Sampling Configuration (Performance C1)

**Problem**: No sampling configuration means all traces are collected, which will saturate the OTEL collector under production load.

**Amendment**:
- Add `OTEL_TRACES_SAMPLER` env var support (default: `parentbased_traceidratio`)
- Add `OTEL_TRACES_SAMPLER_ARG` env var (default: `0.1` = 10% sampling in production)
- Health probes (`/health`, `/ready`) excluded from tracing via URL filter
- Document sampling configuration in deployment docs

### Critical: MCP Config N+1 Queries (Performance C2)

**Problem**: Per-conversation MCP config loading queries the database on every conversation start without caching.

**Amendment**:
- Add TTL cache (5 minutes) for user MCP server configs in `ApollosAIMCPConfig`
- Cache key: `user_id` (invalidated on MCP server CRUD operations)
- Use simple stdlib dict with `time.monotonic()` TTL — no external dependency needed
- MCP CRUD endpoints must invalidate the cache for the affected user

### High: Credential Encryption (Security H1)

**Problem**: Implementation plan stores `config_json`, `webhook_secret`, and other credentials as plaintext JSON/Text columns.

**Amendment**:
- All sensitive fields (`config_json`, `webhook_secret`, `bot_token`, `api_key`, `credentials`, `refresh_token`) must use `SecretsStore` encryption (AES-256-GCM)
- Follow existing `EncryptedSecret` model pattern with AAD binding (`user_id:org_id`)
- `IntegrationConfig.config_json` → encrypted via SecretsStore, not stored as plain `JSON` column
- `UserMCPServer.config_json` → encrypted, especially for env vars and API keys

### High: Enum Consolidation (Architecture C2)

**Problem**: `IntegrationType` (storage model) and `SourceType` (integration model) are duplicate enums.

**Amendment**:
- Single source of truth: `IntegrationType` in `apollosai/integrations/models.py`
- Storage models import from `apollosai.integrations.models`, not define their own
- Add `OPENHANDS = 'openhands'` value only in `SourceType` if needed for internal events
- If both are needed, `SourceType` extends `IntegrationType` or aliased

### High: `__import__` Hack Removal (Architecture)

**Problem**: `IntegrationConversation` model uses `__import__('sqlalchemy').JSON` inline.

**Amendment**:
- Use standard `from sqlalchemy import JSON` at module top
- Column name collision with Python `metadata` is solved by using `sa.Column('metadata', JSON)` pattern or renaming to `extra_metadata`

### High: Audit Route Authorization (Security)

**Problem**: `org_id` as Query parameter enables IDOR — users can query other orgs' audit logs.

**Amendment**:
- `org_id` must be a path parameter: `GET /api/admin/orgs/{org_id}/audit`
- Validate requesting user has admin role in the specified org (not just any org)
- All admin routes follow pattern: `/api/admin/orgs/{org_id}/...`

### High: Integration List Scoping (Security)

**Problem**: `get_integrations` route has no WHERE clause, returning all orgs' configs.

**Amendment**:
- Add `WHERE IntegrationConfig.org_id == current_user.org_id` to all integration queries
- Derive `org_id` from authenticated user context, never from request parameters

### High: Webhook Payload Handling (Architecture)

**Problem**: `handle_webhook` calls `await request.json()` unconditionally, crashes on non-JSON payloads.

**Amendment**:
- Wrap in try/except, return 400 for invalid JSON
- Slack sends `application/x-www-form-urlencoded` for some events — handle content-type dispatch
- Add `Content-Type` check before parsing

### High: Registration Side Effects (Architecture)

**Problem**: Integration registration via `import apollosai.integrations.github` triggers side effects at import time.

**Amendment**:
- Move registration to an explicit `register_all_integrations()` function called during app startup
- Each integration module provides a `register()` classmethod, not module-level `register_integration()` call
- `apollosai/integrations/__init__.py` exports `register_all_integrations()`, not bare imports

### High: Health Probe Redis Connection (Performance)

**Problem**: `check_redis_health()` creates a new Redis client per probe call.

**Amendment**:
- Accept an optional Redis client parameter (dependency injection)
- Reuse the application's Redis connection pool (from rate limiter)
- Fall back to creating a temporary client only if no pool available

### High: Audit Log Indexes (Performance)

**Problem**: `AuditLog` model has no indexes, causing full table scans on admin queries.

**Amendment**:
- Add composite index: `(org_id, created_at DESC)` — covers the primary query pattern
- Add index on `actor_id` for actor-filtered queries
- Add index on `action` for action-filtered queries

### High: Database Migration Strategy (Architecture)

**Problem**: 9 new models in a single Alembic migration is risky and hard to debug.

**Amendment**:
- Split into 2 migrations:
  1. `003a_phase3_monitoring.py` — `audit_log` table
  2. `003b_phase3_integrations.py` — `integration_config`, `integration_conversation`, `user_mcp_server` tables
- Per-integration credential tables (`github_installation`, `slack_workspace`, etc.) can be a third migration or deferred to when each integration is implemented

### Medium: OTEL Thread Safety (Performance)

**Problem**: `_initialized` global flag is not thread-safe.

**Amendment**:
- Use `threading.Lock` to protect `init_otel()` initialization
- Or use `once` pattern (initialize in lifespan `__aenter__` which is single-threaded)

### Medium: IntegrationConversation Indexes (Performance)

**Problem**: Missing indexes for the primary lookup pattern.

**Amendment**:
- Add composite unique index: `(integration_type, external_id, org_id)` — prevents duplicate conversation mappings
- Add index on `conversation_id` for reverse lookups

### Medium: UserMCPServer Indexes (Performance)

**Problem**: Missing index for per-user MCP config loading.

**Amendment**:
- Add composite index: `(user_id, org_id, enabled)` — covers the MCP config query

### Medium: Frontend Branding XSS (Security)

**Problem**: `useBranding` hook sets `favicon_url` without sanitization.

**Amendment**:
- Validate favicon URL is HTTPS and matches an allowlist of domains (or is a relative path)
- Sanitize `app_primary_color` — must match CSS color pattern (hex, rgb, hsl)
- `app_display_name` must be plain text (no HTML)

### Medium: Webhook Rate Limiting (Performance)

**Problem**: No rate limiting on webhook endpoints allows DoS.

**Amendment**:
- Per-integration, per-org rate limit on webhook endpoints (e.g., 100 req/min per integration per org)
- Separate from user API rate limits
- Return 429 with `Retry-After` header

### Medium: Feature Hiding vs App Mode (Architecture) — DEFERRED

**Problem**: Feature hiding conflates `app_mode === 'saas'` with "ApollosAI mode" — these may diverge.

**Verification**: `app_mode` is already used across 15+ frontend files for conditional rendering. Introducing a parallel `feature_flags.admin_panels_enabled` mechanism would create inconsistency with the established codebase pattern.

**Decision**: Keep using `app_mode` for Phase 3 (matches existing codebase). Revisit only if we need to differentiate features within a single mode. Adding granular feature flags now is YAGNI.

### Low: Git Commit Hygiene (Implementation)

**Problem**: Task 32 uses `git add -A` which can stage sensitive files.

**Amendment**:
- All tasks must use `git add <specific-file>` per project convention
- Never use `git add .` or `git add -A`

---

## Independent Verification (2026-02-17)

> Verification conducted against codebase reality after initial review amendments were documented.

### Verified Against Codebase

| Finding | Verified? | Evidence |
|---------|-----------|----------|
| BYOMCP Command Injection | **Confirmed** | `MCPStdioServerConfig` validates format but not content (`mcp_config.py:71-195`) |
| V0 MonitoringListener | **Confirmed** | Line 1: `"scheduled for removal April 1, 2026"`. No V1 equivalent exists |
| OTEL Sampling | **Confirmed** | Default SDK behavior = `AlwaysOn` sampler (100% traces) |
| MCP N+1 Queries | **Confirmed** | `session.py:208` calls `create_default_mcp_server_config()` per conversation |
| Credential Encryption | **Confirmed** | Existing `encrypt_utils.py` provides AES-256-GCM; plan used plaintext |
| Enum Duplication | **Confirmed** | Plan defined `IntegrationType` and `SourceType` with same values |
| Audit Route IDOR | **Confirmed** | Plan used `Query(...)` for `org_id`; existing routes use `Path(...)` |
| Integration List Scoping | **Confirmed** | Plan had `select(IntegrationConfig)` with no WHERE clause |
| `__import__` Hack | **Confirmed** | Plan literally had `type_=__import__('sqlalchemy').JSON` |
| Registration Side Effects | **Confirmed** | Plan registered integrations at import time in `__init__.py` |
| Redis Connection Leak | **Confirmed** | Plan created new `aioredis.from_url()` per health probe call |
| Audit Log Indexes | **Confirmed** | No existing ApollosAI models use explicit `Index()` definitions |
| Webhook Auth (HMAC) | **Confirmed** | Enterprise uses `hmac.compare_digest` (`jira_dc_manager.py:148`) |
| Microsoft Scopes | **Partially** | Over-permissioning valid; "scope escalation via refresh" is not how MSAL works |
| Feature Hiding vs App Mode | **Deferred** | `app_mode` used in 15+ frontend files; adding parallel flags = YAGNI |
| MCP Config Module-Level | **Not an issue** | `os.environ.setdefault()` before import is the standard extension mechanism |

### Corrections Applied During Verification

1. **SQLAlchemy imports**: Fixed `sa.Index(...)` → `Index(...)` with proper imports (matching codebase convention)
2. **`cachetools` dependency**: Replaced with stdlib `time.monotonic()` TTL dict (no new dependency)
3. **Webhook prefix**: Noted `/api/webhooks/` is organizational clarity, not a security fix
4. **Microsoft scope**: Corrected "scope escalation" language — real risk is over-requesting at consent time

---

## Validation Review (2026-02-17)

> Independent 4-dimensional review (Security, Architecture, Performance, Correctness) conducted by parallel review team.
> All 16 original findings confirmed. All 4 corrections verified. 11 additional findings identified.
> Amendments below marked with **REVIEW V2:** prefix in the implementation plan.

### High: MCP TTL Cache Unbounded Growth (Performance H1)

**Problem**: `ApollosAIMCPConfig._cache` class-level dict has no upper bound. Under high user load, cache grows indefinitely.

**Amendment**:
- Add `_cache_max_size = 1000` class attribute
- Evict oldest entry (by timestamp) when cache reaches capacity
- Implementation updated in Task 17

### High: MCP Cache Async Concurrency (Performance H2)

**Problem**: Class-level `dict` accessed by multiple async coroutines. While CPython's GIL prevents true data races for simple dict ops, this is fragile for complex access patterns.

**Amendment**:
- Document that simple dict get/set is GIL-safe in CPython
- If access patterns become complex (multi-key operations), migrate to `asyncio.Lock`
- Current implementation is acceptable for single-key get/set/delete

### High: CSS Color Regex Too Permissive (Security H3)

**Problem**: `[a-zA-Z]+$` branch in color validation regex allows any alphabetic string (e.g., `expression`, `inherit`), not just valid CSS colors.

**Amendment**:
- Tightened regex to match only hex, rgb(), and hsl() with numeric arguments
- Removed named color branch entirely — named colors are uncommon in branding configs
- Implementation updated in Task 25 (useBranding hook)

### Medium: SQLAlchemy Enum Column Extensibility (Architecture M1)

**Problem**: `Enum(IntegrationType)` creates a PostgreSQL ENUM type. Adding new integration types later requires an ALTER TYPE migration.

**Amendment**:
- Documented trade-off: Enum provides DB-level validation but requires migration for new values
- For Phase 3, Enum is acceptable since integration types change infrequently
- If integration types become dynamic (user-defined), migrate to `String` column with app-level validation
- Implementation noted in Task 3 (IntegrationConfig model)

### Medium: SourceType Backward-Compat Migration Path (Architecture M2)

**Problem**: `SourceType = IntegrationType` alias works but existing enterprise code should be migrated over time.

**Amendment**:
- Added `__all__` to `apollosai/integrations/models.py` to control exports
- Documented migration path: replace `SourceType` references with `IntegrationType` across enterprise code
- Implementation updated in Task 9

### Medium: shutdown_otel Holds Lock During Network I/O (Performance M3)

**Problem**: `_init_lock` held while calling `tp.shutdown()` and `mp.shutdown()`, which may flush spans/metrics over the network, blocking other threads.

**Amendment**:
- Set `_initialized = False` inside lock, then release lock before performing shutdown I/O
- Prevents other threads from waiting on network operations during shutdown
- Implementation updated in Task 5

### Medium: Webhook Route Leaks Internal Errors (Security M4)

**Problem**: `receive_webhook` route propagates unhandled exceptions as 500 responses with stack traces.

**Amendment**:
- Wrap `manager.handle_webhook(request)` in try/except
- Log exception internally, return generic `{"error": "internal_error"}` with 500 status
- Implementation updated in Task 11

### Medium: handle_webhook Returns 200 for Errors (Architecture M5)

**Problem**: `handle_webhook()` returns dict (auto-serialized as 200 OK) for errors like `invalid_signature`, `unsupported_content_type`, `invalid_payload`.

**Amendment**:
- Return `JSONResponse(status_code=401, ...)` for signature failures
- Return `JSONResponse(status_code=400, ...)` for bad payloads
- Implementation updated in Task 10 (base manager)

### Low: Missing __all__ in Integration Models (Architecture L1)

**Problem**: No `__all__` export list in `apollosai/integrations/models.py`.

**Amendment**:
- Added `__all__` listing public exports
- Implementation updated in Task 9

### Low: Audit Log Index Missing DESC on created_at (Performance L2)

**Problem**: `Index('ix_audit_log_org_created', 'org_id', 'created_at')` doesn't specify descending order for the typical "most recent first" query.

**Amendment**:
- Updated index to use `postgresql_ops={'created_at': 'DESC'}` for descending sort optimization
- Implementation updated in Task 1

### Low: OTEL ParentBasedTraceIdRatio Class Name Incorrect (Correctness L3)

**Problem**: `ParentBasedTraceIdRatio` is not a real OpenTelemetry SDK class. Correct usage is `ParentBased(root=TraceIdRatioBased(...))`.

**Amendment**:
- Fixed import: `from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased`
- Fixed construction: `ParentBased(root=TraceIdRatioBased(sampler_arg))`
- Implementation updated in Task 5

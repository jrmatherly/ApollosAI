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

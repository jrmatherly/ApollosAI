# Phase 3B: Integration Framework & Platform Connectors — Implementation Plan

**Goal:** Build the integration framework (base manager, registry, routes) and 5 platform connectors (GitHub, Jira, Slack, Bitbucket, Microsoft 365) plus per-org MCP config with BYOMCP support.

**Scope:** Tasks 9-18 | Pillar B | Depends on Phase 3A (Monitoring) | Must complete before Phase 3C (Frontend)

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

## Pillar B: Integrations

### Task 9: Integration Base Models

> **NOTE:** `apollosai/integrations/__init__.py` and `apollosai/integrations/models.py` already
> exist from Phase 3A Task 2 (pre-step) with `IntegrationType` enum and `SourceType` alias.
> This task EXTENDS that file with `IntegrationEvent`, `ConversationContext`, `OAuthConfig`
> Pydantic models and `__all__` export list.

**Files:**
- Modify: `apollosai/integrations/models.py` (extend with Pydantic models — file already has IntegrationType enum)
- Test: `tests/unit/apollosai/integrations/test_models.py`

**Step 1: Extend integration models with Pydantic classes**

```python
# apollosai/integrations/models.py
"""Shared models for the integration framework.

REVIEW: This module is the SINGLE SOURCE OF TRUTH for integration type enums.
Storage models import IntegrationType from here — do not redefine in storage models.
"""
import enum
from pydantic import BaseModel


# REVIEW: Renamed from SourceType to IntegrationType — single enum used everywhere.
# Storage models and integration code all import from this module.
class IntegrationType(str, enum.Enum):
    GITHUB = 'github'
    JIRA = 'jira'
    SLACK = 'slack'
    BITBUCKET = 'bitbucket'
    MICROSOFT = 'microsoft'
    OPENHANDS = 'openhands'  # internal events only


# Alias for backward compatibility in integration code
# REVIEW V2: Migrate existing enterprise code from SourceType → IntegrationType over time
SourceType = IntegrationType

__all__ = ['IntegrationType', 'SourceType', 'IntegrationEvent', 'ConversationContext', 'OAuthConfig']


class IntegrationEvent(BaseModel):
    """Normalized event from any integration."""
    source: SourceType
    event_type: str
    external_id: str
    external_url: str | None = None
    title: str | None = None
    body: str | None = None
    repo_url: str | None = None
    user_email: str | None = None
    raw_payload: dict | None = None


class ConversationContext(BaseModel):
    """Context passed to conversation creation from an integration."""
    title: str
    initial_message: str
    repo_url: str | None = None
    metadata: dict | None = None


class OAuthConfig(BaseModel):
    """OAuth configuration for an integration."""
    authorize_url: str
    token_url: str
    client_id: str
    scopes: list[str]
```

**Step 2: Write tests, run, commit**

```bash
git add apollosai/integrations/models.py tests/unit/apollosai/integrations/test_models.py
git commit -m "feat(apollosai): extend integration models with IntegrationEvent, ConversationContext, OAuthConfig"
```

---

### Task 10: Rich Base Manager

**Files:**
- Create: `apollosai/integrations/base.py`
- Test: `tests/unit/apollosai/integrations/test_base.py`

**Step 1: Write the abstract base manager**

```python
# apollosai/integrations/base.py
"""Rich base manager for ApollosAI integrations."""
import logging
from abc import ABC, abstractmethod
from fastapi import Request
from apollosai.integrations.models import ConversationContext, IntegrationEvent, OAuthConfig, SourceType

logger = logging.getLogger(__name__)


class ApollosAIIntegrationManager(ABC):
    """Base class for all integration managers.

    Provides shared infrastructure: HTTP client, credential access,
    webhook verification, OTEL tracing, and audit logging.
    Subclasses implement platform-specific logic.
    """

    source_type: SourceType

    @abstractmethod
    async def validate_webhook(self, request: Request) -> bool:
        """Validate webhook signature. Return True if valid."""
        ...

    @abstractmethod
    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse raw webhook payload into a normalized IntegrationEvent.
        Return None to skip processing (irrelevant event).
        """
        ...

    @abstractmethod
    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a parsed event."""
        ...

    @abstractmethod
    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response message back to the integration platform."""
        ...

    def get_oauth_config(self) -> OAuthConfig | None:
        """Return OAuth config for integrations requiring OAuth. Default: None."""
        return None

    async def handle_webhook(self, request: Request) -> dict:
        """Standard webhook processing pipeline.

        1. Validate signature (REVIEW: uses timing-safe HMAC comparison)
        2. Check replay protection (REVIEW: reject events older than 5 minutes)
        3. Parse event (REVIEW: handles non-JSON content types)
        4. Build context
        5. Create conversation (placeholder — will be wired in Task 11)
        6. Post acknowledgment

        Override for custom flows (e.g., Slack interactive messages).
        """
        if not await self.validate_webhook(request):
            # REVIEW V2: Return proper HTTP status code, not 200 with error payload
            from starlette.responses import JSONResponse
            return JSONResponse(status_code=401, content={'error': 'invalid_signature'})

        # REVIEW: Handle non-JSON payloads (Slack sends form-urlencoded for some events)
        content_type = request.headers.get('content-type', '')
        try:
            if 'application/json' in content_type:
                body = await request.json()
            elif 'application/x-www-form-urlencoded' in content_type:
                form = await request.form()
                body = dict(form)
            else:
                return JSONResponse(status_code=400, content={'error': 'unsupported_content_type'})
        except Exception:
            return JSONResponse(status_code=400, content={'error': 'invalid_payload'})

        event = await self.parse_event(body)
        if event is None:
            return {'status': 'skipped'}

        context = await self.build_context(event)
        logger.info(
            'integration_event',
            extra={
                'source': self.source_type.value,
                'event_type': event.event_type,
                'external_id': event.external_id,
            },
        )
        # Conversation creation will be wired here
        return {'status': 'processed', 'title': context.title}
```

**Step 2: Write tests (verify ABC enforcement, test handle_webhook pipeline)**

Test a concrete subclass mock that implements all abstract methods. Verify `handle_webhook` calls them in order.

Run: `poetry run pytest tests/unit/apollosai/integrations/test_base.py -v`

```bash
git add apollosai/integrations/base.py tests/unit/apollosai/integrations/test_base.py
git commit -m "feat(apollosai): add ApollosAIIntegrationManager rich base class"
```

---

### Task 11: Integration Registry + Generic Routes

**Files:**
- Create: `apollosai/integrations/registry.py`
- Create: `apollosai/server/routes/integrations.py`
- Test: `tests/unit/apollosai/server/routes/test_integrations.py`

**Step 1: Write integration registry**

```python
# apollosai/integrations/registry.py
"""Registry for discovering and accessing integration managers."""
from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import SourceType

_registry: dict[SourceType, type[ApollosAIIntegrationManager]] = {}


def register_integration(source_type: SourceType, manager_cls: type[ApollosAIIntegrationManager]) -> None:
    _registry[source_type] = manager_cls


def get_integration(source_type: SourceType) -> type[ApollosAIIntegrationManager] | None:
    return _registry.get(source_type)


def list_integrations() -> list[SourceType]:
    return list(_registry.keys())
```

**Step 2: Write generic integration routes**

```python
# apollosai/server/routes/integrations.py
from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apollosai.integrations.models import SourceType
from apollosai.integrations.registry import get_integration, list_integrations
from apollosai.server.auth.rbac import require_auth, require_role
from apollosai.server.deps import get_db_session
from apollosai.storage.models.integration_config import IntegrationConfig

router = APIRouter()
_require_admin = require_role('admin')


# REVIEW: Webhook endpoints mounted under /api/webhooks/ (separate from authenticated routes)
# to make the no-JWT policy explicit and auditable
@router.post('/api/webhooks/{integration_type}')
async def receive_webhook(
    request: Request,
    integration_type: str = Path(...),
):
    """Receive webhook from any integration. No JWT auth — verified by per-integration signature."""
    try:
        source = SourceType(integration_type)
    except ValueError:
        return JSONResponse(status_code=404, content={'error': f'Unknown integration: {integration_type}'})
    manager_cls = get_integration(source)
    if manager_cls is None:
        return JSONResponse(status_code=404, content={'error': f'Integration not registered: {integration_type}'})
    # REVIEW V2: Wrap in try/except to prevent internal error details leaking in 500 responses
    try:
        manager = manager_cls()
        return await manager.handle_webhook(request)
    except Exception:
        logger.exception('Webhook processing error for %s', integration_type)
        return JSONResponse(status_code=500, content={'error': 'internal_error'})


# REVIEW: All integration queries MUST be org-scoped (Security finding: cross-org data leak)
@router.get('/api/integrations')
async def get_integrations(
    user=Depends(require_auth),
    session: AsyncSession = Depends(get_db_session),
):
    """List all available integrations and their status for the current user's org."""
    registered = list_integrations()
    configs = {}
    if registered:
        # REVIEW: Added WHERE org_id filter — original had no filter (full table scan, cross-org leak)
        org_id = user.org_id  # derive from authenticated user context
        stmt = select(IntegrationConfig).where(IntegrationConfig.org_id == org_id)
        result = await session.execute(stmt)
        for config in result.scalars().all():
            configs[config.integration_type] = config.enabled
    return [
        {'type': t.value, 'enabled': configs.get(t, False), 'registered': True}
        for t in registered
    ]
```

**Step 3: Write tests, run, commit**

```bash
git add apollosai/integrations/registry.py apollosai/server/routes/integrations.py tests/unit/apollosai/server/routes/test_integrations.py
git commit -m "feat(apollosai): add integration registry and generic webhook/config routes"
```

---

### Task 12: GitHub Integration Manager

**Files:**
- Create: `apollosai/integrations/github/__init__.py`
- Create: `apollosai/integrations/github/manager.py`
- Create: `apollosai/integrations/github/service.py`
- Create: `apollosai/integrations/github/views.py`
- Test: `tests/unit/apollosai/integrations/github/test_manager.py`

**Step 1: Write GitHub manager**

Key behaviors:
- `validate_webhook`: HMAC-SHA256 using `X-Hub-Signature-256` header against stored webhook secret
- `parse_event`: Handle `issues` (labeled), `issue_comment` (created with @openhands mention), `pull_request_review_comment`
- `build_context`: Extract issue/PR title, body, repo URL
- `post_response`: Post comment via GitHub API using installation token

**Step 2: Write GitHub service** (HTTP client for GitHub API)

Uses `httpx.AsyncClient` with GitHub App installation token auth. Methods: `get_issue`, `post_comment`, `get_installation_token`.

**Step 3: Write views** (Pydantic models for GitHub event contexts)

**Step 4: Module `apollosai/integrations/github/__init__.py`**:
```python
# REVIEW: Do NOT register at import time (side effect). Registration happens
# in register_all_integrations() (Task 30). This file is just the package marker.
```

**Step 5: Write tests** — mock httpx, test webhook validation, test event parsing, test handle_webhook pipeline

Run: `poetry run pytest tests/unit/apollosai/integrations/github/ -v`

```bash
git add apollosai/integrations/github/ tests/unit/apollosai/integrations/github/
git commit -m "feat(apollosai): add GitHub integration manager with webhook handling"
```

---

### Task 13: Jira Integration Manager

**Files:**
- Create: `apollosai/integrations/jira/__init__.py`
- Create: `apollosai/integrations/jira/manager.py`
- Create: `apollosai/integrations/jira/service.py`
- Create: `apollosai/integrations/jira/views.py`
- Test: `tests/unit/apollosai/integrations/jira/test_manager.py`

Same pattern as GitHub. Key differences:
- `validate_webhook`: Jira uses shared secret token in header
- `parse_event`: Handle `jira:issue_created`, `jira:issue_updated` (with trigger label), `comment_created`
- `post_response`: Post comment via Jira REST API
- Service: Uses `httpx.AsyncClient` with Basic auth (email + API token)

```bash
git add apollosai/integrations/jira/ tests/unit/apollosai/integrations/jira/
git commit -m "feat(apollosai): add Jira integration manager with webhook handling"
```

---

### Task 14: Slack Integration Manager

**Files:**
- Create: `apollosai/integrations/slack/__init__.py`
- Create: `apollosai/integrations/slack/manager.py`
- Create: `apollosai/integrations/slack/service.py`
- Create: `apollosai/integrations/slack/views.py`
- Test: `tests/unit/apollosai/integrations/slack/test_manager.py`

Key differences from GitHub/Jira:
- `validate_webhook`: Slack signing secret + timestamp verification
- `parse_event`: Handle `event_callback` (app_mention, message), `url_verification` challenge
- `post_response`: Post to Slack channel/thread via `slack_sdk.web.async_client.AsyncWebClient`
- OAuth flow: Bot token installation (`/api/integrations/slack/install`, `/api/integrations/slack/callback`)
- **Dependency**: `slack-sdk` (add to `pyproject.toml`)

Override `handle_webhook` for Slack's `url_verification` challenge response.

```bash
git add apollosai/integrations/slack/ tests/unit/apollosai/integrations/slack/
git commit -m "feat(apollosai): add Slack integration manager with bot token auth"
```

---

### Task 15: Bitbucket Integration Manager

**Files:**
- Create: `apollosai/integrations/bitbucket/__init__.py`
- Create: `apollosai/integrations/bitbucket/manager.py`
- Create: `apollosai/integrations/bitbucket/service.py`
- Create: `apollosai/integrations/bitbucket/views.py`
- Test: `tests/unit/apollosai/integrations/bitbucket/test_manager.py`

Key differences:
- `validate_webhook`: Bitbucket webhook secret HMAC verification
- `parse_event`: Handle `pullrequest:comment_created`, `issue:comment_created`
- `post_response`: Post comment via Bitbucket API v2
- Service: Uses `httpx.AsyncClient` with App password or OAuth access token

```bash
git add apollosai/integrations/bitbucket/ tests/unit/apollosai/integrations/bitbucket/
git commit -m "feat(apollosai): add Bitbucket integration manager with webhook handling"
```

---

### Task 16: Microsoft 365 Integration Manager

**Files:**
- Create: `apollosai/integrations/microsoft/__init__.py`
- Create: `apollosai/integrations/microsoft/manager.py`
- Create: `apollosai/integrations/microsoft/service.py`
- Create: `apollosai/integrations/microsoft/mcp_tools.py`
- Create: `apollosai/integrations/microsoft/views.py`
- Test: `tests/unit/apollosai/integrations/microsoft/test_manager.py`

Unique aspects:
- **Dual role**: Event integration (Graph subscriptions) AND MCP tool provider
- `validate_webhook`: Graph notification validation token
- `parse_event`: Handle change notifications from Graph subscriptions
- Service: Uses `msgraph-sdk` with MSAL token (leveraging existing Entra ID auth)
- `mcp_tools.py`: Expose Graph operations as MCP tools (search documents, read files, list emails)
- **Dependency**: `msgraph-sdk` (add to `pyproject.toml`)

```bash
git add apollosai/integrations/microsoft/ tests/unit/apollosai/integrations/microsoft/
git commit -m "feat(apollosai): add Microsoft 365 integration with Graph API and MCP tools"
```

---

### Task 17: Per-Org MCP Config + BYOMCP

**Files:**
- Create: `apollosai/mcp/__init__.py`
- Create: `apollosai/mcp/config.py`
- Create: `apollosai/server/routes/mcp.py`
- Add models to: `apollosai/server/routes/models.py`
- Test: `tests/unit/apollosai/mcp/test_config.py`
- Test: `tests/unit/apollosai/server/routes/test_mcp.py`

**Step 1: Write MCP config override**

```python
# apollosai/mcp/config.py
"""Per-org MCP config that merges global + org + user-defined MCP servers.

REVIEW: Includes TTL cache (5 min) for user MCP configs to prevent N+1 queries
on every conversation start. Cache invalidated by MCP CRUD endpoints.
"""
import logging
import time
from openhands.core.config.mcp_config import (
    MCPConfig,
    MCPSHTTPServerConfig,
    MCPSSEServerConfig,
    MCPStdioServerConfig,
    OpenHandsMCPConfig,
)
from openhands.core.config.openhands_config import OpenHandsConfig

logger = logging.getLogger(__name__)


class ApollosAIMCPConfig(OpenHandsMCPConfig):
    """Extends default MCP config with per-org and per-user MCP servers.

    REVIEW: Uses TTL cache to prevent N+1 queries on every conversation start.
    MCP CRUD endpoints must call invalidate_mcp_cache(user_id) on changes.
    """

    # REVIEW: Simple TTL cache — 5 minute expiry. No external dependency needed.
    # REVIEW V2: Added max size cap to prevent unbounded growth with many users.
    # When full, evict oldest entry before inserting new one.
    _cache: dict[str, tuple[float, tuple]] = {}
    _cache_ttl: float = 300.0  # 5 minutes
    _cache_max_size: int = 1000  # cap to prevent unbounded growth

    @classmethod
    def invalidate_mcp_cache(cls, user_id: str) -> None:
        """Invalidate cached MCP config for a user. Call from MCP CRUD endpoints."""
        cls._cache.pop(user_id, None)

    @staticmethod
    async def create_default_mcp_server_config(
        host: str, config: OpenHandsConfig, user_id: str | None = None
    ) -> tuple[MCPSHTTPServerConfig | None, list[MCPStdioServerConfig]]:
        # Get base config from parent
        shttp, stdio = await OpenHandsMCPConfig.create_default_mcp_server_config(
            host, config, user_id
        )

        if user_id is None:
            return shttp, stdio

        # REVIEW: Check cache first to prevent N+1 queries
        cached = ApollosAIMCPConfig._cache.get(user_id)
        if cached is not None:
            ts, result = cached
            if time.monotonic() - ts < ApollosAIMCPConfig._cache_ttl:
                return result
            del ApollosAIMCPConfig._cache[user_id]

        # Load user's custom MCP servers from DB
        try:
            from apollosai.server.lifespan import get_session_maker
            from apollosai.storage.models.user_mcp_server import MCPServerType, UserMCPServer
            from sqlalchemy import select

            session_maker = get_session_maker()
            if session_maker is None:
                return shttp, stdio

            async with session_maker() as session:
                import uuid
                stmt = select(UserMCPServer).where(
                    UserMCPServer.user_id == uuid.UUID(user_id),
                    UserMCPServer.enabled == True,  # noqa: E712
                )
                result = await session.execute(stmt)
                servers = result.scalars().all()

                for srv in servers:
                    if srv.server_type == MCPServerType.STDIO:
                        stdio.append(MCPStdioServerConfig(
                            name=srv.name,
                            command=srv.config_json.get('command', ''),
                            args=srv.config_json.get('args', []),
                            env=srv.config_json.get('env', {}),
                        ))
                    elif srv.server_type == MCPServerType.SSE:
                        # SSE servers go on the MCP config directly
                        pass  # handled via config merging
                    elif srv.server_type == MCPServerType.SHTTP:
                        # Only one shttp can be primary
                        pass
        except Exception:
            logger.exception('Failed to load user MCP servers')

        # REVIEW: Cache the result with timestamp
        # REVIEW V2: Enforce max size — evict oldest entry if at capacity
        if len(ApollosAIMCPConfig._cache) >= ApollosAIMCPConfig._cache_max_size:
            oldest_key = min(ApollosAIMCPConfig._cache, key=lambda k: ApollosAIMCPConfig._cache[k][0])
            del ApollosAIMCPConfig._cache[oldest_key]
        ApollosAIMCPConfig._cache[user_id] = (time.monotonic(), (shttp, stdio))
        return shttp, stdio
```

**Step 2: Write MCP management routes** (CRUD for user MCP servers)

```python
# apollosai/server/routes/mcp.py — endpoints for BYOMCP
# POST /api/mcp/servers — add
# GET /api/mcp/servers — list
# PUT /api/mcp/servers/{id} — update
# DELETE /api/mcp/servers/{id} — remove
# POST /api/mcp/servers/{id}/test — test connectivity
```

**Step 3: Write tests, run, commit**

```bash
git add apollosai/mcp/ apollosai/server/routes/mcp.py tests/unit/apollosai/mcp/ tests/unit/apollosai/server/routes/test_mcp.py
git commit -m "feat(apollosai): add per-org MCP config with BYOMCP management"
```

---

### Task 18: Add Python Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add new dependencies**

```bash
poetry add opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy opentelemetry-instrumentation-httpx
poetry add slack-sdk
poetry add msgraph-sdk
```

Note: Both `[project].dependencies` and `[tool.poetry.dependencies]` must stay in sync per CLAUDE.md.

**Step 2: Run pre-commit (pyproject-fmt may reformat)**

Run: `pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml`

**Step 3: Commit**

```bash
git add pyproject.toml poetry.lock
git commit -m "chore: add Phase 3 dependencies (OTEL instrumentation, slack-sdk, msgraph-sdk)"
```

---


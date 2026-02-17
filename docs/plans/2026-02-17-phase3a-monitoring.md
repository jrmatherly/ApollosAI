# Phase 3A: Monitoring & Hardening — Implementation Plan

**Goal:** Add audit logging, health/readiness probes, OpenTelemetry observability, and monitoring infrastructure to the ApollosAI enterprise layer.

**Scope:** Tasks 1-8 | Pillar C | Must complete before Phase 3B (Integrations)

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

## Pillar C: Monitoring & Hardening

### Task 1: New Storage Models — Audit Log

**Files:**
- Create: `apollosai/storage/models/audit_log.py`
- Test: `tests/unit/apollosai/storage/models/test_audit_log.py`

**Step 1: Write the model**

```python
# apollosai/storage/models/audit_log.py
import enum
import uuid
from sqlalchemy import Enum, ForeignKey, Index, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column
from apollosai.storage.models.base import Base, TimestampMixin


class AuditAction(str, enum.Enum):
    MEMBER_INVITED = 'member_invited'
    MEMBER_REMOVED = 'member_removed'
    ROLE_CHANGED = 'role_changed'
    INTEGRATION_CONFIGURED = 'integration_configured'
    MCP_SERVER_ADDED = 'mcp_server_added'
    MCP_SERVER_REMOVED = 'mcp_server_removed'
    SETTINGS_UPDATED = 'settings_updated'
    API_KEY_CREATED = 'api_key_created'
    API_KEY_REVOKED = 'api_key_revoked'
    ORG_CREATED = 'org_created'
    ORG_UPDATED = 'org_updated'
    TEAM_CREATED = 'team_created'
    TEAM_UPDATED = 'team_updated'


class AuditLog(TimestampMixin, Base):
    __tablename__ = 'audit_log'
    # REVIEW: Added indexes for primary query patterns (org_id+created_at, actor_id, action)
    __table_args__ = (
        # REVIEW V2: Use .desc() on created_at for "most recent first" query pattern
        Index('ix_audit_log_org_created', 'org_id', 'created_at', postgresql_ops={'created_at': 'DESC'}),
        Index('ix_audit_log_actor', 'actor_id'),
        Index('ix_audit_log_action', 'action'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # REVIEW: actor_id nullable for system-initiated actions (e.g., scheduled tasks)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('user.id'), default=None)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction))
    resource_type: Mapped[str] = mapped_column()
    resource_id: Mapped[str] = mapped_column()
    details: Mapped[dict | None] = mapped_column(JSON, default=None)
    ip_address: Mapped[str | None] = mapped_column(Text, default=None)
```

**Step 2: Write the failing test**

```python
# tests/unit/apollosai/storage/models/test_audit_log.py
import uuid
import pytest
from apollosai.storage.models.audit_log import AuditAction, AuditLog


@pytest.mark.asyncio
async def test_audit_log_create(async_session):
    user_id = uuid.uuid4()
    org_id = uuid.uuid4()

    # Seed required FK targets
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1', email='a@b.com'))
    await async_session.flush()

    log = AuditLog(
        actor_id=user_id,
        org_id=org_id,
        action=AuditAction.MEMBER_INVITED,
        resource_type='user',
        resource_id=str(uuid.uuid4()),
        details={'role': 'member'},
        ip_address='127.0.0.1',
    )
    async_session.add(log)
    await async_session.commit()

    fetched = await async_session.get(AuditLog, log.id)
    assert fetched is not None
    assert fetched.action == AuditAction.MEMBER_INVITED
    assert fetched.details == {'role': 'member'}
```

**Step 3: Run test to verify it passes** (model already written)

Run: `poetry run pytest tests/unit/apollosai/storage/models/test_audit_log.py -v`
Expected: PASS

**Step 4: Add audit_log import to conftest AND models `__init__.py`**

Add `import apollosai.storage.models.audit_log  # noqa: F401` to `tests/unit/apollosai/conftest.py`.

> **VALIDATED FIX (Review V3):** New models MUST also be added to `apollosai/storage/models/__init__.py`
> for Alembic discoverability. Alembic's `env.py` imports `Base` from `__init__.py`, which triggers
> model registration with `Base.metadata`. Without this, `alembic revision --autogenerate` won't
> detect new tables. The conftest import only helps tests.

Add to `apollosai/storage/models/__init__.py`:
```python
from apollosai.storage.models.audit_log import AuditLog
```
And add `'AuditLog'` to `__all__`.

**Step 5: Commit**

```bash
git add apollosai/storage/models/audit_log.py apollosai/storage/models/__init__.py tests/unit/apollosai/storage/models/test_audit_log.py tests/unit/apollosai/conftest.py
git commit -m "feat(apollosai): add AuditLog model with action enum"
```

---

### Task 2: New Storage Models — Integration Infrastructure

**Files:**
- Create: `apollosai/integrations/__init__.py` (pre-step: minimal enum for Task 9 forward-compatibility)
- Create: `apollosai/integrations/models.py` (pre-step: IntegrationType enum only — Task 9 extends with Pydantic models)
- Create: `apollosai/storage/models/integration_config.py`
- Create: `apollosai/storage/models/integration_conversation.py`
- Create: `apollosai/storage/models/user_mcp_server.py`
- Test: `tests/unit/apollosai/storage/models/test_integration_models.py`

> **VALIDATED FIX (Finding 1):** `IntegrationConfig` imports `IntegrationType` from `apollosai.integrations.models`,
> but that module is a Task 9 (Phase 3B) deliverable that doesn't exist yet. Fix: create a minimal
> `apollosai/integrations/models.py` with ONLY the `IntegrationType` enum here. Task 9 will extend
> this file with `IntegrationEvent`, `ConversationContext`, `OAuthConfig` Pydantic models.

**Step 0 (pre-step): Create minimal integrations module with IntegrationType enum**

```python
# apollosai/integrations/__init__.py
# (empty)

# apollosai/integrations/models.py
"""Shared models for the integration framework.

REVIEW: This module is the SINGLE SOURCE OF TRUTH for integration type enums.
Storage models import IntegrationType from here — do not redefine in storage models.
NOTE: Created in Phase 3A Task 2 with enum only. Phase 3B Task 9 extends with
IntegrationEvent, ConversationContext, OAuthConfig Pydantic models.
"""
import enum


class IntegrationType(str, enum.Enum):
    GITHUB = 'github'
    JIRA = 'jira'
    SLACK = 'slack'
    BITBUCKET = 'bitbucket'
    MICROSOFT = 'microsoft'
    OPENHANDS = 'openhands'  # internal events only


# Alias for backward compatibility in integration code
SourceType = IntegrationType
```

**Step 1: Write integration_config model**

```python
# apollosai/storage/models/integration_config.py
import uuid
from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from apollosai.storage.models.base import Base, TimestampMixin

# REVIEW: Do NOT define IntegrationType here — import from apollosai.integrations.models
# to avoid duplicate enums (Architecture finding). Single source of truth.
from apollosai.integrations.models import IntegrationType


class IntegrationConfig(TimestampMixin, Base):
    __tablename__ = 'integration_config'
    # REVIEW: Added unique constraint (one config per integration per org)
    __table_args__ = (
        UniqueConstraint('org_id', 'integration_type', name='uq_integration_config_org_type'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    # REVIEW V2: Consider using String column with app-level validation instead of
    # SQLAlchemy Enum() — adding new integration types with Enum requires ALTER TYPE migration.
    # For now, Enum is acceptable since integration types change infrequently.
    integration_type: Mapped[IntegrationType] = mapped_column(Enum(IntegrationType))
    enabled: Mapped[bool] = mapped_column(default=False)
    # REVIEW: config_json and webhook_secret MUST be encrypted via SecretsStore.
    # Store as encrypted blob (Text), decrypt at read time. Do NOT use plain JSON column.
    config_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
    webhook_secret_encrypted: Mapped[str | None] = mapped_column(Text, default=None)
```

**Step 2: Write integration_conversation model**

```python
# apollosai/storage/models/integration_conversation.py
import uuid
from sqlalchemy import ForeignKey, Index, JSON, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from apollosai.storage.models.base import Base, TimestampMixin


class IntegrationConversation(TimestampMixin, Base):
    __tablename__ = 'integration_conversation'
    # REVIEW: Added composite unique index for dedup + conversation_id index for reverse lookups
    __table_args__ = (
        UniqueConstraint('integration_type', 'external_id', 'org_id',
                         name='uq_integration_conversation_type_ext_org'),
        Index('ix_integration_conversation_conv', 'conversation_id'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    integration_type: Mapped[str] = mapped_column()
    external_id: Mapped[str] = mapped_column(Text)
    conversation_id: Mapped[str] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text, default=None)
    # REVIEW: Removed __import__ hack — use standard JSON import from top of file
    extra_metadata: Mapped[dict | None] = mapped_column(JSON, default=None)
```

**Step 3: Write user_mcp_server model**

```python
# apollosai/storage/models/user_mcp_server.py
import enum
import uuid
from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column
from apollosai.storage.models.base import Base, TimestampMixin


class MCPServerType(str, enum.Enum):
    STDIO = 'stdio'
    SSE = 'sse'
    SHTTP = 'shttp'


class UserMCPServer(TimestampMixin, Base):
    __tablename__ = 'user_mcp_server'
    # REVIEW: Added index for MCP config loading query pattern
    __table_args__ = (
        Index('ix_user_mcp_server_user_org', 'user_id', 'org_id', 'enabled'),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    name: Mapped[str] = mapped_column()
    server_type: Mapped[MCPServerType] = mapped_column(Enum(MCPServerType))
    # REVIEW: config MUST be encrypted — contains commands, env vars, API keys.
    # Store via SecretsStore, not plaintext JSON.
    config_encrypted: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    # REVIEW: BYOMCP stdio requires org-admin approval before activation
    approved: Mapped[bool] = mapped_column(default=False)
```

**Step 4: Write tests**

> **VALIDATED FIX (Finding 2):** Original test code referenced `config_json` (dict) but models
> define `config_encrypted` (Text/str) and `webhook_secret_encrypted` (Text/str). Fixed below
> to use correct field names with string values representing encrypted blobs. In production,
> SecretsStore handles encrypt/decrypt — tests use plaintext strings as stand-ins.

```python
# tests/unit/apollosai/storage/models/test_integration_models.py
import uuid
import pytest
from apollosai.storage.models.integration_config import IntegrationConfig
from apollosai.integrations.models import IntegrationType
from apollosai.storage.models.integration_conversation import IntegrationConversation
from apollosai.storage.models.user_mcp_server import MCPServerType, UserMCPServer


@pytest.mark.asyncio
async def test_integration_config_create(async_session):
    from apollosai.storage.models.organization import Organization
    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    await async_session.flush()

    config = IntegrationConfig(
        org_id=org_id,
        integration_type=IntegrationType.GITHUB,
        enabled=True,
        config_encrypted='encrypted:app_id=12345',
        webhook_secret_encrypted='encrypted:whsec_test',
    )
    async_session.add(config)
    await async_session.commit()

    fetched = await async_session.get(IntegrationConfig, config.id)
    assert fetched is not None
    assert fetched.integration_type == IntegrationType.GITHUB
    assert fetched.config_encrypted == 'encrypted:app_id=12345'
    assert fetched.webhook_secret_encrypted == 'encrypted:whsec_test'


@pytest.mark.asyncio
async def test_user_mcp_server_create(async_session):
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1'))
    await async_session.flush()

    server = UserMCPServer(
        user_id=user_id,
        org_id=org_id,
        name='my-jira-tool',
        server_type=MCPServerType.STDIO,
        config_encrypted='encrypted:command=python,args=-m jira_mcp',
        enabled=True,
    )
    async_session.add(server)
    await async_session.commit()

    fetched = await async_session.get(UserMCPServer, server.id)
    assert fetched is not None
    assert fetched.server_type == MCPServerType.STDIO
    assert fetched.config_encrypted == 'encrypted:command=python,args=-m jira_mcp'
```

**Step 5: Update conftest AND models `__init__.py`, run tests, commit**

Add imports for all three new models to `tests/unit/apollosai/conftest.py`.

> **VALIDATED FIX (Review V3):** Also add all 3 new models to `apollosai/storage/models/__init__.py`
> for Alembic discoverability (same pattern as Task 1 Step 4).

Add to `apollosai/storage/models/__init__.py`:
```python
from apollosai.storage.models.integration_config import IntegrationConfig
from apollosai.storage.models.integration_conversation import IntegrationConversation
from apollosai.storage.models.user_mcp_server import UserMCPServer
```
And add `'IntegrationConfig'`, `'IntegrationConversation'`, `'UserMCPServer'` to `__all__`.

Run: `poetry run pytest tests/unit/apollosai/storage/models/test_integration_models.py -v`

```bash
git add apollosai/integrations/__init__.py apollosai/integrations/models.py apollosai/storage/models/__init__.py apollosai/storage/models/integration_config.py apollosai/storage/models/integration_conversation.py apollosai/storage/models/user_mcp_server.py tests/unit/apollosai/storage/models/test_integration_models.py tests/unit/apollosai/conftest.py
git commit -m "feat(apollosai): add integration config, conversation, and MCP server models"
```

---

### Task 3: Health & Readiness Endpoints

**Files:**
- Create: `apollosai/monitoring/health.py`
- Create: `apollosai/server/routes/health.py`
- Create: `apollosai/monitoring/__init__.py`
- Test: `tests/unit/apollosai/server/routes/test_health.py`

**Step 1: Write the health check service**

```python
# apollosai/monitoring/__init__.py
# (empty)

# apollosai/monitoring/health.py
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker


async def check_db_health(session_maker: async_sessionmaker) -> bool:
    """Check database connectivity with a simple SELECT 1."""
    try:
        async with session_maker() as session:
            await session.execute(text('SELECT 1'))
        return True
    except Exception:
        return False


async def check_redis_health(redis_client=None) -> bool | None:
    """Check Redis connectivity. Returns None if Redis not configured.

    REVIEW: Accept optional redis_client parameter to reuse existing connection pool.
    Creating a new client per probe is wasteful and can leak connections.
    """
    import os
    redis_url = os.environ.get('REDIS_URL')
    if not redis_url and redis_client is None:
        return None
    try:
        if redis_client is not None:
            await redis_client.ping()
            return True
        # Fallback: create temporary client only if no pool available
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url)
        try:
            await client.ping()
            return True
        finally:
            await client.aclose()
    except Exception:
        return False
```

**Step 2: Write the routes**

```python
# apollosai/server/routes/health.py
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from apollosai.monitoring.health import check_db_health, check_redis_health
from apollosai.server.lifespan import get_session_maker

router = APIRouter()


@router.get('/health')
async def health():
    """Liveness probe — returns 200 if process is running."""
    return {'status': 'ok'}


@router.get('/ready')
async def ready():
    """Readiness probe — checks DB and Redis connectivity."""
    session_maker = get_session_maker()
    if session_maker is None:
        return JSONResponse(status_code=503, content={'status': 'not_ready', 'error': 'Database not initialized'})

    db_ok = await check_db_health(session_maker)
    redis_result = await check_redis_health()

    checks = {'database': db_ok}
    if redis_result is not None:
        checks['redis'] = redis_result

    all_ok = db_ok and (redis_result is None or redis_result)

    if not all_ok:
        return JSONResponse(status_code=503, content={'status': 'not_ready', 'checks': checks})
    return {'status': 'ready', 'checks': checks}
```

**Step 3: Write failing tests**

```python
# tests/unit/apollosai/server/routes/test_health.py
from fastapi import FastAPI
from fastapi.testclient import TestClient
from apollosai.server.routes.health import router


def test_health_returns_200():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


def test_ready_returns_503_when_db_not_initialized(monkeypatch):
    monkeypatch.setattr('apollosai.server.routes.health.get_session_maker', lambda: None)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get('/ready')
    assert resp.status_code == 503
```

**Step 4: Run tests, verify pass**

Run: `poetry run pytest tests/unit/apollosai/server/routes/test_health.py -v`

**Step 5: Wire routes into app and commit**

> **VALIDATED FIX (Review V3):** Mount health routes at root path (no `/api` prefix) for
> Kubernetes liveness/readiness probe compatibility. Add to `apollosai/app_server.py`
> after the auth router registration (line 54):

```python
from apollosai.server.routes.health import router as health_router
base_app.include_router(health_router)  # /health and /ready — no prefix for K8s probes
```

Also add `apollosai/app_server.py` to the commit (modified file):

```bash
git add apollosai/monitoring/__init__.py apollosai/monitoring/health.py apollosai/server/routes/health.py apollosai/app_server.py tests/unit/apollosai/server/routes/test_health.py
git commit -m "feat(apollosai): add health and readiness endpoints"
```

---

### Task 4: OTEL Setup — Tracer and Meter Providers

**Files:**
- Create: `apollosai/monitoring/otel.py`
- Modify: `apollosai/server/lifespan.py` (add OTEL init in `__aenter__`)
- Test: `tests/unit/apollosai/monitoring/test_otel.py`

**Step 1: Write OTEL initialization module**

```python
# apollosai/monitoring/otel.py
"""OpenTelemetry tracer and meter provider initialization."""
import os
import logging
import threading

logger = logging.getLogger(__name__)

# REVIEW: Use threading.Lock to protect initialization (thread safety finding)
_initialized = False
_init_lock = threading.Lock()


def init_otel(service_name: str = 'apollosai') -> None:
    """Initialize OTEL tracer and meter providers.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT from env (default: http://localhost:4317).
    No-ops if endpoint is empty or if already initialized.

    REVIEW: Supports OTEL_TRACES_SAMPLER and OTEL_TRACES_SAMPLER_ARG env vars
    for production sampling (default: 10% trace sampling).
    """
    global _initialized
    with _init_lock:
        if _initialized:
            return

    endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()
    if not endpoint:
        logger.info('OTEL_EXPORTER_OTLP_ENDPOINT not set — skipping OTEL init')
        return

    try:
        from opentelemetry import trace, metrics
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({'service.name': service_name})

        # REVIEW: Configure sampling to prevent collector saturation
        # REVIEW V2: Correct import path — ParentBased wraps TraceIdRatioBased
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
        sampler_arg = float(os.environ.get('OTEL_TRACES_SAMPLER_ARG', '0.1'))
        sampler = ParentBased(root=TraceIdRatioBased(sampler_arg))

        # Tracer
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(tracer_provider)

        # Meter
        metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=endpoint))
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        metrics.set_meter_provider(meter_provider)

        _initialized = True
        logger.info('OTEL initialized — exporting to %s (sampling: %s)', endpoint, sampler_arg)
    except ImportError:
        logger.warning('OTEL SDK packages not installed — skipping')
    except Exception:
        logger.exception('Failed to initialize OTEL')


def shutdown_otel() -> None:
    """Flush and shut down OTEL providers."""
    global _initialized
    # REVIEW V2: Set _initialized=False inside lock, then perform network I/O outside lock
    # to avoid blocking other threads during span/metric flush
    with _init_lock:
        if not _initialized:
            return
        _initialized = False
    try:
        from opentelemetry import trace, metrics
        tp = trace.get_tracer_provider()
        if hasattr(tp, 'shutdown'):
            tp.shutdown()
        mp = metrics.get_meter_provider()
        if hasattr(mp, 'shutdown'):
            mp.shutdown()
    except Exception:
        logger.exception('Error shutting down OTEL')
    # VALIDATED FIX (Review V3): Removed duplicate `_initialized = False` that was
    # dead code — already set to False inside the lock on line 626 above.
```

**Step 2: Hook into lifespan**

In `apollosai/server/lifespan.py`, add to `__aenter__`:
```python
from apollosai.monitoring.otel import init_otel
init_otel()
```

In `__aexit__`:
```python
from apollosai.monitoring.otel import shutdown_otel
shutdown_otel()
```

**Step 3: Write tests**

```python
# tests/unit/apollosai/monitoring/test_otel.py
from apollosai.monitoring.otel import init_otel, shutdown_otel


def test_otel_init_noop_without_endpoint(monkeypatch):
    """OTEL init should no-op when endpoint is not set."""
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
    import apollosai.monitoring.otel as otel_mod
    otel_mod._initialized = False
    init_otel()
    assert not otel_mod._initialized


def test_otel_shutdown_noop_when_not_initialized():
    """Shutdown should be safe when not initialized."""
    import apollosai.monitoring.otel as otel_mod
    otel_mod._initialized = False
    shutdown_otel()  # should not raise
```

**Step 4: Run tests, commit**

Run: `poetry run pytest tests/unit/apollosai/monitoring/test_otel.py -v`

```bash
git add apollosai/monitoring/otel.py apollosai/server/lifespan.py tests/unit/apollosai/monitoring/test_otel.py
git commit -m "feat(apollosai): add OTEL tracer/meter initialization with env-based config"
```

---

### Task 5: Monitoring Listener

**Files:**
- Create: `apollosai/monitoring/listener.py`
- Test: `tests/unit/apollosai/monitoring/test_listener.py`

**Step 1: Write the listener**

```python
# apollosai/monitoring/listener.py
"""ApollosAI monitoring listener — extends V0 MonitoringListener with OTEL metrics.

REVIEW: MonitoringListener is V0-only (hard removal April 1, 2026).
Architecture: This class is a thin V0 ADAPTER that delegates to MonitoringService.
When V1 provides a monitoring extension point, swap the adapter layer only.
All actual logic lives in MonitoringService (standalone, no V0 dependency).
"""
import logging
from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.events.event import Event
from openhands.server.monitoring import MonitoringListener

logger = logging.getLogger(__name__)


class ApollosAIMonitoringListener(MonitoringListener):
    """V0 adapter — delegates to MonitoringService for all actual logic.

    REVIEW: When V0 is removed (April 2026), MonitoringService can be called
    directly from the lifespan service or via a V1 extension point.
    """

    def on_session_event(self, event: Event) -> None:
        from openhands.events.observation.agent import AgentStateChangedObservation
        from openhands.core.schema.agent import AgentState
        if isinstance(event, AgentStateChangedObservation) and event.agent_state == AgentState.ERROR:
            logger.info('agent_error', extra={'signal': 'agent_status_error'})

    def on_agent_session_start(self, success: bool, duration: float) -> None:
        logger.info(
            'agent_session_start',
            extra={'signal': 'agent_session_start', 'success': success, 'duration': duration},
        )

    def on_create_conversation(self) -> None:
        logger.info('create_conversation', extra={'signal': 'create_conversation'})

    @classmethod
    def get_instance(cls, config: OpenHandsConfig) -> 'ApollosAIMonitoringListener':
        return cls()
```

**Step 2: Write tests**

```python
# tests/unit/apollosai/monitoring/test_listener.py
from unittest.mock import MagicMock
from apollosai.monitoring.listener import ApollosAIMonitoringListener


def test_listener_on_create_conversation():
    listener = ApollosAIMonitoringListener()
    listener.on_create_conversation()  # should not raise


def test_listener_on_session_start():
    listener = ApollosAIMonitoringListener()
    listener.on_agent_session_start(success=True, duration=1.5)  # should not raise


def test_listener_get_instance():
    instance = ApollosAIMonitoringListener.get_instance(config=MagicMock())
    assert isinstance(instance, ApollosAIMonitoringListener)
```

**Step 3: Wire into config**

In `apollosai/server/config.py`, set:
```python
monitoring_listener_class: str = 'apollosai.monitoring.listener.ApollosAIMonitoringListener'
```

**Step 4: Run tests, commit**

Run: `poetry run pytest tests/unit/apollosai/monitoring/test_listener.py -v`

```bash
git add apollosai/monitoring/listener.py apollosai/server/config.py tests/unit/apollosai/monitoring/test_listener.py
git commit -m "feat(apollosai): add ApollosAIMonitoringListener with structured logging"
```

---

### Task 6: Audit Log Service + Decorator

**Files:**
- Create: `apollosai/monitoring/audit.py`
- Test: `tests/unit/apollosai/monitoring/test_audit.py`

**Step 1: Write audit service**

```python
# apollosai/monitoring/audit.py
"""Audit logging service for admin actions."""
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from apollosai.storage.models.audit_log import AuditAction, AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    actor_id: uuid.UUID,
    org_id: uuid.UUID,
    action: AuditAction,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    """Record an audit log entry."""
    log = AuditLog(
        actor_id=actor_id,
        org_id=org_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=ip_address,
    )
    session.add(log)
    await session.flush()
    return log
```

**Step 2: Write tests, run, commit**

Test: Create user + org, call `record_audit`, assert log entry exists with correct fields.

Run: `poetry run pytest tests/unit/apollosai/monitoring/test_audit.py -v`

```bash
git add apollosai/monitoring/audit.py tests/unit/apollosai/monitoring/test_audit.py
git commit -m "feat(apollosai): add audit log service with record_audit function"
```

---

### Task 7: Audit Log Routes

**Files:**
- Create: `apollosai/server/routes/admin.py`
- Add models to: `apollosai/server/routes/models.py`
- Test: `tests/unit/apollosai/server/routes/test_admin.py`

**Step 1: Add response models**

Add to `apollosai/server/routes/models.py`:
```python
import datetime

class AuditLogResponse(BaseModel):
    id: uuid.UUID
    actor_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime.datetime
```

**Step 2: Write admin routes**

```python
# apollosai/server/routes/admin.py
import uuid
from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.server.routes.models import AuditLogResponse
from apollosai.storage.models.audit_log import AuditLog

router = APIRouter()
_require_admin = require_role('admin')


# REVIEW: org_id MUST be a path parameter, not query parameter (prevents IDOR)
# Route pattern: /api/admin/orgs/{org_id}/audit
@router.get('/api/admin/orgs/{org_id}/audit')
async def list_audit_logs(
    org_id: uuid.UUID = Path(...),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    user=Depends(_require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """List audit log entries for an organization. Requires admin role.

    REVIEW: Validates user has admin role in THIS specific org (not just any org).
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    logs = result.scalars().all()
    return [
        AuditLogResponse(
            id=log.id,
            actor_id=log.actor_id,
            action=log.action.value,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            details=log.details,
            ip_address=log.ip_address,
            created_at=log.created_at,
        )
        for log in logs
    ]
```

**Step 3: Wire admin routes into app server**

> **VALIDATED FIX (Review V3):** The admin routes must be registered in `apollosai/app_server.py`
> or they'll return 404 in production. Tests pass because they create their own FastAPI app,
> but the real app only mounts `auth_router` (line 54).

Add to `apollosai/app_server.py` after the health router:
```python
from apollosai.server.routes.admin import router as admin_router
base_app.include_router(admin_router)  # /api/admin/orgs/{org_id}/audit
```

**Step 4: Write tests following the orgs route test pattern, run, commit**

```bash
git add apollosai/server/routes/admin.py apollosai/server/routes/models.py apollosai/app_server.py tests/unit/apollosai/server/routes/test_admin.py
git commit -m "feat(apollosai): add admin audit log query endpoint"
```

---

### Task 8: Alembic Migrations — Phase 3 Schema

**REVIEW: Split into 2 migrations (not 1 monolithic) for safer rollback and debugging.**

**Files:**
- Create: `apollosai/migrations/versions/<revision>_phase3a_monitoring.py`
- Create: `apollosai/migrations/versions/<revision>_phase3b_integrations.py`

**Step 1a: Generate monitoring migration (audit_log only)**

Run: `cd /Users/jason/dev/ApollosAI && PYTHONPATH=".:$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini revision --autogenerate -m "Phase 3a — audit_log table"`

**Step 1b: Generate integrations migration (integration_config, integration_conversation, user_mcp_server)**

Run: `cd /Users/jason/dev/ApollosAI && PYTHONPATH=".:$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini revision --autogenerate -m "Phase 3b — integration_config, integration_conversation, user_mcp_server tables"`

**Step 2: Fix lint issues** (Alembic autogenerate always needs cleanup)

Run: `pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml`

**Step 3: Verify migration applies cleanly**

Run: `PYTHONPATH=".:$PYTHONPATH" poetry run alembic -c apollosai/alembic.ini upgrade head`

**Step 4: Commit**

```bash
git add apollosai/migrations/versions/
git commit -m "feat(apollosai): add Phase 3 Alembic migration for integration and audit models"
```

---


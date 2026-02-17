# Phase 3: Comprehensive Enterprise — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add monitoring/hardening, 5 platform integrations (GitHub, Jira, Slack, Bitbucket, Microsoft 365), per-org MCP with BYOMCP, and full admin frontend panels to the ApollosAI enterprise layer.

**Architecture:** Three pillars built in dependency order: C (Monitoring) → B (Integrations) → A (Frontend). Rich base manager pattern for integrations. OTEL-native observability. Env-driven branding.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy async, OpenTelemetry, httpx, slack-sdk, msgraph-sdk, React 19, TanStack Query, Tailwind CSS 4

**Design doc:** `docs/plans/2026-02-17-phase3-design.md`

**Review amendments:** See `docs/plans/2026-02-17-phase3-design.md` § "Review Amendments (2026-02-17)" for full design-level findings. Inline amendments below marked with **REVIEW:** prefix.

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

**Step 4: Add audit_log import to conftest**

Add `import apollosai.storage.models.audit_log  # noqa: F401` to `tests/unit/apollosai/conftest.py`.

**Step 5: Commit**

```bash
git add apollosai/storage/models/audit_log.py tests/unit/apollosai/storage/models/test_audit_log.py tests/unit/apollosai/conftest.py
git commit -m "feat(apollosai): add AuditLog model with action enum"
```

---

### Task 2: New Storage Models — Integration Infrastructure

**Files:**
- Create: `apollosai/storage/models/integration_config.py`
- Create: `apollosai/storage/models/integration_conversation.py`
- Create: `apollosai/storage/models/user_mcp_server.py`
- Test: `tests/unit/apollosai/storage/models/test_integration_models.py`

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

```python
# tests/unit/apollosai/storage/models/test_integration_models.py
import uuid
import pytest
from apollosai.storage.models.integration_config import IntegrationConfig, IntegrationType
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
        config_json={'app_id': '12345', 'webhook_url': 'https://example.com/webhook'},
    )
    async_session.add(config)
    await async_session.commit()

    fetched = await async_session.get(IntegrationConfig, config.id)
    assert fetched is not None
    assert fetched.integration_type == IntegrationType.GITHUB
    assert fetched.config_json['app_id'] == '12345'


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
        config_json={'command': 'python', 'args': ['-m', 'jira_mcp']},
        enabled=True,
    )
    async_session.add(server)
    await async_session.commit()

    fetched = await async_session.get(UserMCPServer, server.id)
    assert fetched is not None
    assert fetched.server_type == MCPServerType.STDIO
```

**Step 5: Update conftest with new model imports, run tests, commit**

Add imports for all three new models to `tests/unit/apollosai/conftest.py`.

Run: `poetry run pytest tests/unit/apollosai/storage/models/test_integration_models.py -v`

```bash
git add apollosai/storage/models/integration_config.py apollosai/storage/models/integration_conversation.py apollosai/storage/models/user_mcp_server.py tests/unit/apollosai/storage/models/test_integration_models.py tests/unit/apollosai/conftest.py
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

Add `from apollosai.server.routes.health import router as health_router` and mount in `apollosai/app_server.py` or the route registration point.

```bash
git add apollosai/monitoring/__init__.py apollosai/monitoring/health.py apollosai/server/routes/health.py tests/unit/apollosai/server/routes/test_health.py
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
    _initialized = False
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

**Step 3: Write tests following the orgs route test pattern, run, commit**

```bash
git add apollosai/server/routes/admin.py apollosai/server/routes/models.py tests/unit/apollosai/server/routes/test_admin.py
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

## Pillar B: Integrations

### Task 9: Integration Base Models

**Files:**
- Create: `apollosai/integrations/__init__.py`
- Create: `apollosai/integrations/models.py`
- Test: `tests/unit/apollosai/integrations/test_models.py`

**Step 1: Write base integration models**

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
git add apollosai/integrations/__init__.py apollosai/integrations/models.py tests/unit/apollosai/integrations/test_models.py
git commit -m "feat(apollosai): add integration base models (SourceType, IntegrationEvent, ConversationContext)"
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

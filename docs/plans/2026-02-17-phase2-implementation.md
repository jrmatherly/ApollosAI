# Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all Phase 2 enterprise functionality — DB sessions, store implementations, auth completion, RBAC, CRUD routes, security hardening, and frontend integration.

**Architecture:** Bottom-up incremental layers. Each layer builds on the previous. DB foundation first, then stores, auth, RBAC, security, frontend. Every new feature follows TDD.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, AES-256-GCM, MSAL, React 19, TypeScript, TanStack Query, Zustand.

**Design doc:** `docs/plans/2026-02-17-phase2-design.md`

**Review status:** Reviewed 2026-02-17 by 3 parallel reviewers (security, architecture, testing). 57 deduplicated findings incorporated below. See `## Review Findings Summary` at end of document for the full consolidated list.

**Existing code reference:**
- Injector pattern: `openhands/app_server/services/injector.py`
- V1 DbSessionInjector: `openhands/app_server/services/db_session_injector.py`
- V1 UserContextInjector: `apollosai/server/auth/user_context.py`
- Store stubs: `apollosai/storage/stores/*.py`
- Models: `apollosai/storage/models/*.py`
- DB utilities: `apollosai/storage/database.py`
- Encryption: `apollosai/storage/encrypt_utils.py`
- Auth: `apollosai/server/auth/entraid_auth.py`

---

## Layer 1: DB Foundation

### Task 1: ApollosAI DbSessionInjector

**Files:**
- Create: `apollosai/server/db_session.py`
- Test: `tests/unit/apollosai/server/test_db_session.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/server/test_db_session.py
"""Tests for ApollosAI DbSessionInjector."""

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.db_session import ApollosAIDbSessionInjector


class TestApollosAIDbSessionInjector:
    """Test the ApollosAI DB session injector."""

    def test_is_pydantic_model(self):
        """Injector should be a Pydantic BaseModel (matching V1 pattern)."""
        from pydantic import BaseModel

        assert issubclass(ApollosAIDbSessionInjector, BaseModel)

    def test_requires_database_url(self, monkeypatch):
        """Should raise if DATABASE_URL is not set."""
        monkeypatch.delenv('DATABASE_URL', raising=False)
        with pytest.raises(ValueError, match='DATABASE_URL'):
            ApollosAIDbSessionInjector()

    def test_creates_with_valid_url(self, monkeypatch):
        """Should create successfully with DATABASE_URL set."""
        monkeypatch.setenv('DATABASE_URL', 'postgresql+asyncpg://user:pass@localhost/testdb')
        injector = ApollosAIDbSessionInjector()
        assert injector.database_url == 'postgresql+asyncpg://user:pass@localhost/testdb'

    def test_fixes_postgres_scheme(self, monkeypatch):
        """Should fix postgres:// to postgresql+asyncpg:// scheme."""
        monkeypatch.setenv('DATABASE_URL', 'postgres://user:pass@localhost/testdb')
        injector = ApollosAIDbSessionInjector()
        assert injector.database_url.startswith('postgresql+asyncpg://')

    @pytest.mark.asyncio
    async def test_get_async_session_maker(self, monkeypatch):
        """Should return an async_sessionmaker."""
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        sm = await injector.get_async_session_maker()
        from sqlalchemy.ext.asyncio import async_sessionmaker

        assert isinstance(sm, async_sessionmaker)

    @pytest.mark.asyncio
    async def test_inject_yields_session(self, monkeypatch):
        """Inject should yield an AsyncSession via InjectorState."""
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        from starlette.datastructures import State

        state = State()
        session = None
        async for s in injector.inject(state):
            session = s
        assert session is not None

    @pytest.mark.asyncio
    async def test_inject_rolls_back_on_exception(self, monkeypatch):
        """Session should be rolled back if an error occurs during use.

        Review fix [C1-test]: Rollback path was completely untested.
        """
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        from starlette.datastructures import State

        state = State()
        with pytest.raises(RuntimeError):
            async for session in injector.inject(state):
                raise RuntimeError('simulated error')
        # Session should be cleaned up from state
        assert not hasattr(state, APOLLOSAI_DB_SESSION_ATTR)

    @pytest.mark.asyncio
    async def test_dispose_cleans_up_engine(self, monkeypatch):
        """Dispose should close the engine and clear cached references.

        Review fix [C1-test]: dispose() was untested — engine resource leak.
        """
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        await injector.get_async_session_maker()
        assert injector._async_engine is not None
        await injector.dispose()
        assert injector._async_engine is None
        assert injector._async_session_maker is None
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/apollosai/server/test_db_session.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apollosai.server.db_session'`

**Step 3: Write minimal implementation**

```python
# apollosai/server/db_session.py
"""ApollosAI DbSessionInjector — async PostgreSQL session management.

Simplified version of openhands/app_server/services/db_session_injector.py
that uses DATABASE_URL directly instead of DB_HOST/DB_PORT/DB_NAME.
"""

import logging
from collections.abc import AsyncGenerator

from fastapi import Request
from pydantic import BaseModel, PrivateAttr
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from apollosai.storage.database import get_database_url
from openhands.app_server.services.injector import Injector, InjectorState

_logger = logging.getLogger(__name__)
APOLLOSAI_DB_SESSION_ATTR = 'apollosai_db_session'


class ApollosAIDbSessionInjector(BaseModel, Injector[AsyncSession]):
    """Injects async SQLAlchemy sessions backed by ApollosAI's PostgreSQL.

    Review fix [C8]: Generic param is AsyncSession (what inject() yields),
    NOT async_sessionmaker (upstream has same bug — don't propagate it).
    """

    database_url: str = ''
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    _async_engine: AsyncEngine | None = PrivateAttr(default=None)
    _async_session_maker: async_sessionmaker | None = PrivateAttr(default=None)

    def model_post_init(self, __context) -> None:
        if not self.database_url:
            self.database_url = get_database_url()

    async def get_async_db_engine(self) -> AsyncEngine:
        if self._async_engine is None:
            if self.database_url.startswith('sqlite'):
                self._async_engine = create_async_engine(
                    self.database_url, poolclass=NullPool
                )
            else:
                self._async_engine = create_async_engine(
                    self.database_url,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_pre_ping=True,
                )
        return self._async_engine

    async def get_async_session_maker(self) -> async_sessionmaker:
        if self._async_session_maker is None:
            engine = await self.get_async_db_engine()
            self._async_session_maker = async_sessionmaker(
                engine, class_=AsyncSession, expire_on_commit=False
            )
        return self._async_session_maker

    async def dispose(self) -> None:
        """Dispose the engine — call on shutdown."""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            self._async_session_maker = None

    async def inject(
        self, state: InjectorState, request: Request | None = None
    ) -> AsyncGenerator[AsyncSession, None]:
        """Inject an async session, caching on state for reuse within a request."""
        db_session = getattr(state, APOLLOSAI_DB_SESSION_ATTR, None)
        if db_session:
            yield db_session
        else:
            session_maker = await self.get_async_session_maker()
            db_session = session_maker()
            try:
                setattr(state, APOLLOSAI_DB_SESSION_ATTR, db_session)
                yield db_session
                await db_session.commit()
            except Exception:
                _logger.exception('Rolling back SQL due to error')
                await db_session.rollback()
                raise
            finally:
                if hasattr(state, APOLLOSAI_DB_SESSION_ATTR):
                    delattr(state, APOLLOSAI_DB_SESSION_ATTR)
                await db_session.close()
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/unit/apollosai/server/test_db_session.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add apollosai/server/db_session.py tests/unit/apollosai/server/test_db_session.py
git commit -m "feat(apollosai): add ApollosAI DbSessionInjector for async PostgreSQL sessions"
```

---

### Task 2: Wire Lifespan Engine Init/Dispose

**Files:**
- Modify: `apollosai/server/lifespan.py`
- Test: `tests/unit/apollosai/server/test_lifespan.py` (modify existing)

**Step 1: Write the failing test**

Add to existing `tests/unit/apollosai/server/test_lifespan.py`:

```python
@pytest.mark.asyncio
async def test_lifespan_initializes_db_injector(monkeypatch):
    """Lifespan should initialize the DbSessionInjector on enter."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    from apollosai.server.lifespan import ApollosAILifespanService

    service = ApollosAILifespanService()
    assert hasattr(service, 'db_injector') or hasattr(service, '_db_injector')


@pytest.mark.asyncio
async def test_lifespan_exposes_session_maker(monkeypatch):
    """Lifespan should store db_injector for use by stores."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    from apollosai.server.lifespan import ApollosAILifespanService

    service = ApollosAILifespanService()
    assert service.db_injector is not None


@pytest.mark.asyncio
async def test_lifespan_enter_exit_lifecycle(monkeypatch):
    """Review fix [H1+M3-test]: Engine should init on enter, dispose on exit.

    Without __aenter__/__aexit__, engine leaks connections on every restart.
    """
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    from apollosai.server.lifespan import ApollosAILifespanService

    service = ApollosAILifespanService()
    async with service:
        assert service.db_injector is not None
        assert service.db_injector._async_engine is not None
    # After exit, engine should be disposed
    assert service.db_injector._async_engine is None


@pytest.mark.asyncio
async def test_module_level_session_maker_available_after_enter(monkeypatch):
    """Review fix [C1]: V0 stores need module-level access to session_maker.

    After lifespan enters, get_session_maker() should return a usable maker.
    """
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    from apollosai.server.lifespan import ApollosAILifespanService, get_session_maker

    service = ApollosAILifespanService()
    async with service:
        sm = get_session_maker()
        assert sm is not None
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/apollosai/server/test_lifespan.py -v -k "db_injector"`
Expected: FAIL with `AttributeError: 'ApollosAILifespanService' object has no attribute 'db_injector'`

**Step 3: Write minimal implementation**

Update `apollosai/server/lifespan.py`:

```python
"""ApollosAI lifespan service — manages startup/shutdown for the enterprise server.

Review fixes incorporated:
- [H1]: Override __aenter__/__aexit__ to init engine on startup, dispose on shutdown
- [C1]: Module-level singleton for V0 store bridge (get_session_maker())
"""

import os

from sqlalchemy.ext.asyncio import async_sessionmaker

from openhands.app_server.app_lifespan.oss_app_lifespan_service import (
    OssAppLifespanService,
)

# Module-level singleton for V0 store bridge [C1]
# Populated by __aenter__, cleared by __aexit__
_session_maker: async_sessionmaker | None = None


def get_session_maker() -> async_sessionmaker | None:
    """Get the module-level session maker for V0 store bridge.

    Review fix [C1]: V0 stores instantiated via get_instance(config, user_id)
    have no path to receive a session_maker through the ABC interface.
    This module-level singleton is populated during lifespan startup
    and provides the bridge until stores are migrated to V1 DI.
    """
    return _session_maker


class ApollosAILifespanService(OssAppLifespanService):
    """Enterprise lifespan service.

    Extends OssAppLifespanService to:
    1. Skip OpenHands' SQLite Alembic migrations
    2. Initialize async PostgreSQL engine via ApollosAIDbSessionInjector
    3. Dispose engine on shutdown
    4. Expose session_maker via module-level singleton for V0 stores
    """

    run_alembic_on_startup: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._db_injector = None

    @property
    def db_injector(self):
        """Lazy-init the DB session injector."""
        if self._db_injector is None:
            db_url = os.environ.get('DATABASE_URL', '')
            if db_url:
                from apollosai.server.db_session import ApollosAIDbSessionInjector

                self._db_injector = ApollosAIDbSessionInjector(database_url=db_url)
            else:
                from apollosai.server.db_session import ApollosAIDbSessionInjector

                self._db_injector = ApollosAIDbSessionInjector()
        return self._db_injector

    async def __aenter__(self):
        """Review fix [H1]: Eagerly init engine + expose session_maker."""
        global _session_maker
        await super().__aenter__()
        await self.db_injector.get_async_db_engine()
        _session_maker = await self.db_injector.get_async_session_maker()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        """Review fix [H1]: Dispose engine to prevent connection leaks."""
        global _session_maker
        _session_maker = None
        await self.db_injector.dispose()
        await super().__aexit__(exc_type, exc_value, traceback)
```

**Step 4: Run test to verify it passes**

Run: `poetry run pytest tests/unit/apollosai/server/test_lifespan.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add apollosai/server/lifespan.py tests/unit/apollosai/server/test_lifespan.py
git commit -m "feat(apollosai): wire DbSessionInjector into lifespan service"
```

---

### Task 3: Clean Up Empty Migration Placeholder

**Files:**
- Delete: `apollosai/migrations/versions/bd818a71a520_initial_schema.py`

> **Review fix [M7]:** Only safe to delete if no production DB has run this migration.
> If any DB is at revision `bd818a71a520`, deletion breaks `alembic upgrade head`.
> Since this is Phase 1.5 (pre-production), deletion is safe. The Phase 2 migration
> (Task 4) sets `down_revision = 'faeef06e7fea'` (the real schema migration).

**Step 1: Verify the file is empty (only `pass` in upgrade/downgrade)**

Run: `poetry run pytest tests/unit/apollosai/test_alembic_config.py -v`
Expected: PASS (existing tests still pass after deletion)

**Step 2: Delete the empty placeholder**

```bash
git rm apollosai/migrations/versions/bd818a71a520_initial_schema.py
```

**Step 3: Run Alembic tests to confirm nothing breaks**

Run: `poetry run pytest tests/unit/apollosai/test_alembic_config.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git commit -m "chore(apollosai): remove empty migration placeholder bd818a71a520"
```

---

## Layer 2: Store Implementations

### Task 4: Phase 2 Schema Migration (New Tables)

**Files:**
- Create: `apollosai/storage/models/encrypted_secret.py`
- Create: `apollosai/storage/models/conversation.py`
- Create: `apollosai/storage/models/server_session.py`
- Create: `apollosai/storage/models/revoked_token.py`
- Create: `apollosai/migrations/versions/XXXX_phase2_schema.py` (hand-written)
- Test: `tests/unit/apollosai/storage/models/test_phase2_models.py`

**Step 1: Write the failing test**

```python
# tests/unit/apollosai/storage/models/test_phase2_models.py
"""Tests for Phase 2 models."""

import pytest


class TestEncryptedSecret:
    """Test encrypted_secret model."""

    def test_tablename(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        assert EncryptedSecret.__tablename__ == 'encrypted_secret'

    def test_required_columns(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        columns = {c.name for c in EncryptedSecret.__table__.columns}
        assert {'id', 'user_id', 'org_id', 'key', 'encrypted_value'}.issubset(columns)

    def test_has_timestamps(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        columns = {c.name for c in EncryptedSecret.__table__.columns}
        assert 'created_at' in columns
        assert 'updated_at' in columns


class TestConversation:
    """Test conversation model."""

    def test_tablename(self):
        from apollosai.storage.models.conversation import Conversation

        assert Conversation.__tablename__ == 'conversation'

    def test_required_columns(self):
        from apollosai.storage.models.conversation import Conversation

        columns = {c.name for c in Conversation.__table__.columns}
        assert {'id', 'user_id', 'org_id', 'title', 'created_at'}.issubset(columns)

    def test_has_soft_delete(self):
        from apollosai.storage.models.conversation import Conversation

        columns = {c.name for c in Conversation.__table__.columns}
        assert 'deleted_at' in columns


class TestServerSession:
    """Test server_session model."""

    def test_tablename(self):
        from apollosai.storage.models.server_session import ServerSession

        assert ServerSession.__tablename__ == 'server_session'


class TestRevokedToken:
    """Test revoked_token model."""

    def test_tablename(self):
        from apollosai.storage.models.revoked_token import RevokedToken

        assert RevokedToken.__tablename__ == 'revoked_token'

    def test_has_jti(self):
        from apollosai.storage.models.revoked_token import RevokedToken

        columns = {c.name for c in RevokedToken.__table__.columns}
        assert 'jti' in columns
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/apollosai/storage/models/test_phase2_models.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write the models**

```python
# apollosai/storage/models/encrypted_secret.py
"""Encrypted secret storage per user/org."""

import uuid

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class EncryptedSecret(TimestampMixin, Base):
    __tablename__ = 'encrypted_secret'

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    key: Mapped[str] = mapped_column(String(255))
    encrypted_value: Mapped[str] = mapped_column(Text)

    __table_args__ = (UniqueConstraint('user_id', 'org_id', 'key'),)
```

```python
# apollosai/storage/models/conversation.py
"""Conversation metadata storage scoped to user + org."""

import datetime
import uuid

from sqlalchemy import JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base, TimestampMixin


class Conversation(TimestampMixin, Base):
    __tablename__ = 'conversation'

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('user.id'))
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('organization.id'))
    title: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, default=None)
    deleted_at: Mapped[datetime.datetime | None] = mapped_column(default=None)
```

```python
# apollosai/storage/models/server_session.py
"""Server-side session storage — replaces Starlette cookie sessions."""

import datetime

from sqlalchemy import JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base


class ServerSession(Base):
    __tablename__ = 'server_session'

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    data: Mapped[dict | None] = mapped_column(JSON, default=None)
    expires_at: Mapped[datetime.datetime] = mapped_column(index=True)
    # Review fix [L3]: Index on expires_at for efficient cleanup queries
```

```python
# apollosai/storage/models/revoked_token.py
"""Revoked JWT tracking for token invalidation."""

import datetime

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from apollosai.storage.models.base import Base


class RevokedToken(Base):
    __tablename__ = 'revoked_token'

    jti: Mapped[str] = mapped_column(Text, primary_key=True)
    revoked_at: Mapped[datetime.datetime] = mapped_column()
    expires_at: Mapped[datetime.datetime] = mapped_column()
```

**Step 4: Run tests to verify they pass**

Run: `poetry run pytest tests/unit/apollosai/storage/models/test_phase2_models.py -v`
Expected: All PASS

**Step 4b: Add constraint and index tests**

> Review fix [M13]: Phase 1 model tests only check structure, not constraints.
> Phase 2 must test unique constraints, FK constraints, and nullable settings.

```python
# Add to test_phase2_models.py:

@pytest.mark.asyncio
async def test_encrypted_secret_unique_constraint(async_session):
    """Review fix [M13]: Duplicate (user_id, org_id, key) should raise."""
    from sqlalchemy.exc import IntegrityError
    from apollosai.storage.models.encrypted_secret import EncryptedSecret
    import uuid

    shared = {'user_id': uuid.uuid4(), 'org_id': uuid.uuid4(), 'key': 'LLM_API_KEY'}
    async_session.add(EncryptedSecret(id=uuid.uuid4(), encrypted_value='a', **shared))
    await async_session.commit()
    async_session.add(EncryptedSecret(id=uuid.uuid4(), encrypted_value='b', **shared))
    with pytest.raises(IntegrityError):
        await async_session.commit()


def test_encrypted_secret_user_id_not_nullable():
    """Review fix [M13]: Critical columns must not be nullable."""
    from apollosai.storage.models.encrypted_secret import EncryptedSecret
    col = EncryptedSecret.__table__.columns['user_id']
    assert not col.nullable


def test_server_session_has_expires_at_index():
    """Review fix [L3]: Index on expires_at for efficient cleanup."""
    from apollosai.storage.models.server_session import ServerSession
    indexes = {idx.name for idx in ServerSession.__table__.indexes}
    assert any('expires_at' in str(idx.columns) for idx in ServerSession.__table__.indexes)
```

**Step 5: Write the Alembic migration (hand-written)**

Create `apollosai/migrations/versions/XXXX_phase2_schema.py` with `op.create_table()` calls for all 4 new tables. Use the same pattern as `faeef06e7fea_initial_schema.py`. Set `down_revision = 'faeef06e7fea'`.

> Review fix [M18]: Include a proper `downgrade()` that drops all 4 tables.
> Add a test that verifies upgrade/downgrade round-trip with in-memory SQLite.

**Step 6: Commit**

```bash
git add apollosai/storage/models/encrypted_secret.py apollosai/storage/models/conversation.py \
    apollosai/storage/models/server_session.py apollosai/storage/models/revoked_token.py \
    apollosai/migrations/versions/*_phase2_schema.py \
    tests/unit/apollosai/storage/models/test_phase2_models.py
git commit -m "feat(apollosai): add Phase 2 models and migration (encrypted_secret, conversation, server_session, revoked_token)"
```

---

### Task 4b: DI Wiring — Session Provider + Shared Conftest

> **Review fix [C1+C2]: THE #1 BLOCKER.** Stores and RBAC have no path to get
> DB sessions. The V0 ABC `get_instance(config, user_id)` has no `session_maker`
> param. The V1 `InjectorState` is disconnected from the V0 store path.
>
> **Solution:** Two-pronged approach:
> 1. Module-level singleton in `lifespan.py` (done in Task 2) for V0 bridge
> 2. FastAPI `Depends(get_db_session)` for RBAC and route-level access
> 3. Stores call `get_session_maker()` from lifespan module when not given one

**Files:**
- Create: `apollosai/server/deps.py` (FastAPI dependency functions)
- Create: `tests/unit/apollosai/conftest.py` (shared async_session fixture)
- Test: `tests/unit/apollosai/server/test_deps.py`

**Step 1: Write the shared conftest**

> Review fix [Cross-cutting]: Tasks 4-8 all need the same async SQLite session
> fixture. Extract to `conftest.py` to avoid duplication.

```python
# tests/unit/apollosai/conftest.py
"""Shared fixtures for ApollosAI unit tests."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apollosai.storage.models.base import Base


@pytest.fixture
async def async_engine():
    """Create an in-memory SQLite async engine for testing."""
    engine = create_async_engine('sqlite+aiosqlite://', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def async_session_maker(async_engine):
    """Create an async session maker from the test engine."""
    return async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def async_session(async_session_maker):
    """Create an async session for testing.

    Review fix [H6-test]: Uses try/finally for proper cleanup ordering.
    Session is closed before engine dispose (via fixture dependency chain).
    """
    session = async_session_maker()
    try:
        yield session
    finally:
        await session.close()
```

**Step 2: Write FastAPI dependency for DB sessions**

```python
# apollosai/server/deps.py
"""FastAPI dependency functions for ApollosAI server.

Review fix [C2]: RBAC and routes need DB sessions via Depends().
This module provides get_db_session() for use in route dependencies.
"""

from collections.abc import AsyncGenerator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.lifespan import get_session_maker


async def get_db_session(request: Request | None = None) -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for use in route handlers and RBAC deps.

    Uses the module-level session maker from lifespan (populated on startup).
    """
    session_maker = get_session_maker()
    if session_maker is None:
        raise RuntimeError(
            'Database not initialized. Ensure ApollosAILifespanService has started.'
        )
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
```

**Step 3: Write tests**

```python
# tests/unit/apollosai/server/test_deps.py

import pytest

from apollosai.server.deps import get_db_session


@pytest.mark.asyncio
async def test_get_db_session_raises_when_no_lifespan(monkeypatch):
    """Should raise RuntimeError if session_maker not initialized."""
    monkeypatch.setattr('apollosai.server.deps.get_session_maker', lambda: None)
    with pytest.raises(RuntimeError, match='Database not initialized'):
        async for _ in get_db_session():
            pass


@pytest.mark.asyncio
async def test_get_db_session_yields_session(monkeypatch, async_session_maker):
    """Should yield a working AsyncSession."""
    monkeypatch.setattr('apollosai.server.deps.get_session_maker', lambda: async_session_maker)
    async for session in get_db_session():
        assert session is not None
        from sqlalchemy.ext.asyncio import AsyncSession
        assert isinstance(session, AsyncSession)
```

**Step 4: Commit**

```bash
git add apollosai/server/deps.py tests/unit/apollosai/conftest.py \
    tests/unit/apollosai/server/test_deps.py
git commit -m "feat(apollosai): add DI wiring for DB sessions (V0 bridge + FastAPI Depends)"
```

---

### Task 5: SettingsStore Implementation

**Files:**
- Modify: `apollosai/storage/stores/settings_store.py`
- Modify: `tests/unit/apollosai/storage/stores/test_settings_store.py`

**Step 1: Write the failing tests**

```python
# tests/unit/apollosai/storage/stores/test_settings_store.py
"""Tests for ApollosAISettingsStore — Org -> Team -> User resolution.

Review fixes incorporated:
- [H10]: Replaced `pass` bodies with real assertions
- [M9]: Added full 3-layer resolution chain test
- [M1]: Added get_instance() integration test
- [C2-arch]: Validated Settings field names match model attributes
"""

import uuid

import pytest

from apollosai.storage.stores.settings_store import ApollosAISettingsStore

# NOTE: async_session fixture comes from conftest.py (Task 4b)


class TestSettingsStoreLoad:
    """Test settings resolution chain."""

    @pytest.mark.asyncio
    async def test_load_returns_settings_when_no_db(self):
        """Without a session_maker, should return config defaults (backward compat)."""
        store = ApollosAISettingsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_returns_defaults_when_from_config_returns_none(self, monkeypatch):
        """Review fix [L4]: Settings.from_config() can return None."""
        monkeypatch.setattr(
            'openhands.storage.data_models.settings.Settings.from_config', lambda: None
        )
        store = ApollosAISettingsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_with_session_returns_org_defaults(self, async_session, async_session_maker):
        """With a session, should query org-level LLM defaults."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-4')
        user = User(id=uuid.uuid4(), entra_oid='test-oid', current_org_id=org.id)
        async_session.add_all([org, user])
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings is not None
        assert settings.llm_model == 'gpt-4'

    @pytest.mark.asyncio
    async def test_load_team_overrides_org(self, async_session, async_session_maker):
        """Review fix [H10]: Team-level settings should override org defaults."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-3.5')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team', llm_model='gpt-4')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        async_session.add_all([org, team, user])
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings.llm_model == 'gpt-4'  # Team overrides org

    @pytest.mark.asyncio
    async def test_full_resolution_user_overrides_team_overrides_org(
        self, async_session, async_session_maker
    ):
        """Review fix [M9]: Full 3-layer chain — user wins over team wins over org."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.role import Role
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-3.5')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team', llm_model='gpt-4')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        role = Role(name='member', rank=3)
        async_session.add_all([org, team, user, role])
        await async_session.flush()
        membership = TeamMembership(
            team_id=team.id, user_id=user.id, role_id=role.id, llm_model='claude-3',
        )
        async_session.add(membership)
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings.llm_model == 'claude-3'  # User overrides team overrides org


class TestSettingsStoreStore:
    """Test settings persistence."""

    @pytest.mark.asyncio
    async def test_store_persists_settings(self, async_session, async_session_maker):
        """Review fix [H10]: Store should write to user tier via TeamMembership."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.role import Role
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User
        from openhands.storage.data_models.settings import Settings

        org = Organization(id=uuid.uuid4(), name='test-org')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        role = Role(name='member', rank=3)
        async_session.add_all([org, team, user, role])
        await async_session.flush()
        membership = TeamMembership(
            team_id=team.id, user_id=user.id, role_id=role.id,
        )
        async_session.add(membership)
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        await store.store(Settings(llm_model='gpt-4o'))

        # Reload and verify
        settings = await store.load()
        assert settings.llm_model == 'gpt-4o'


class TestSettingsStoreFieldNames:
    """Review fix [C2-arch]: Verify hardcoded field names exist in Settings."""

    def test_settings_has_expected_fields(self):
        from openhands.storage.data_models.settings import Settings
        field_names = set(Settings.model_fields.keys())
        # These are the field names used in the resolution chain
        for name in ['llm_model', 'llm_base_url', 'max_iterations', 'agent']:
            assert name in field_names, f'{name} not in Settings.model_fields'
```

**Step 2: Run test to verify current stubs produce expected behavior**

Run: `poetry run pytest tests/unit/apollosai/storage/stores/test_settings_store.py -v`
Expected: Some tests fail (the DB-backed ones), stubs pass

**Step 3: Implement the store**

Update `apollosai/storage/stores/settings_store.py`:

```python
"""PostgreSQL-backed settings with Org -> Team -> User resolution.

Review fixes incorporated:
- [C1]: Uses get_session_maker() from lifespan module as V0 bridge
- [H8]: Uses request-scoped sessions via session_maker, not per-operation
- [C2-arch]: Field names verified against Settings.model_fields
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.settings import Settings
from openhands.storage.settings.settings_store import SettingsStore


class ApollosAISettingsStore(SettingsStore):
    """PostgreSQL-backed settings with Org -> Team -> User resolution."""

    def __init__(
        self,
        config: OpenHandsConfig | None,
        user_id: str | None,
        session_maker: async_sessionmaker | None = None,
    ):
        self.config = config
        self.user_id = user_id
        self.session_maker = session_maker

    async def load(self) -> Settings | None:
        """Load settings with Org -> Team -> User resolution chain.

        Falls back to config defaults if no DB session is available.
        """
        if self.session_maker is None or self.user_id is None:
            result = Settings.from_config()
            return result if result is not None else Settings()

        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        async with self.session_maker() as session:
            # Load user to get current org/team context
            user = await session.get(User, self.user_id)
            if user is None:
                result = Settings.from_config()
                return result if result is not None else Settings()

            settings_dict: dict = {}

            # Layer 1: Org defaults
            if user.current_org_id:
                org = await session.get(Organization, user.current_org_id)
                if org:
                    if org.default_llm_model:
                        settings_dict['llm_model'] = org.default_llm_model
                    if org.default_llm_base_url:
                        settings_dict['llm_base_url'] = org.default_llm_base_url
                    if org.default_max_iterations:
                        settings_dict['max_iterations'] = org.default_max_iterations
                    if org.agent:
                        settings_dict['agent'] = org.agent

            # Layer 2: Team overrides
            if user.current_team_id:
                team = await session.get(Team, user.current_team_id)
                if team:
                    if team.llm_model:
                        settings_dict['llm_model'] = team.llm_model
                    if team.llm_base_url:
                        settings_dict['llm_base_url'] = team.llm_base_url
                    if team.max_iterations:
                        settings_dict['max_iterations'] = team.max_iterations

            # Layer 3: User overrides (from TeamMembership)
            if user.current_team_id:
                stmt = select(TeamMembership).where(
                    TeamMembership.team_id == user.current_team_id,
                    TeamMembership.user_id == user.id,
                )
                result = await session.execute(stmt)
                membership = result.scalar_one_or_none()
                if membership:
                    if membership.llm_model:
                        settings_dict['llm_model'] = membership.llm_model
                    if membership.max_iterations:
                        settings_dict['max_iterations'] = membership.max_iterations

            # Build Settings from resolved values
            base = Settings.from_config()
            if base is None:
                base = Settings()
            if settings_dict:
                base = base.model_copy(update=settings_dict)
            return base

    async def store(self, settings: Settings) -> None:
        """Persist settings — stores at user tier via TeamMembership overrides."""
        if self.session_maker is None or self.user_id is None:
            return

        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        async with self.session_maker() as session:
            user = await session.get(User, self.user_id)
            if user is None or user.current_team_id is None:
                return

            stmt = select(TeamMembership).where(
                TeamMembership.team_id == user.current_team_id,
                TeamMembership.user_id == user.id,
            )
            result = await session.execute(stmt)
            membership = result.scalar_one_or_none()
            if membership:
                if settings.llm_model:
                    membership.llm_model = settings.llm_model
                if settings.max_iterations:
                    membership.max_iterations = settings.max_iterations
                await session.commit()

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISettingsStore':
        """Review fix [C1]: Bridge V0 ABC by getting session_maker from lifespan module."""
        from apollosai.server.lifespan import get_session_maker

        return cls(config=config, user_id=user_id, session_maker=get_session_maker())
```

**Step 4: Run tests**

Run: `poetry run pytest tests/unit/apollosai/storage/stores/test_settings_store.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apollosai/storage/stores/settings_store.py tests/unit/apollosai/storage/stores/test_settings_store.py
git commit -m "feat(apollosai): implement SettingsStore with Org->Team->User resolution"
```

---

### Task 6: SecretsStore Implementation

**Files:**
- Modify: `apollosai/storage/stores/secrets_store.py`
- Modify: `tests/unit/apollosai/storage/stores/test_secrets_store.py`

**Step 1: Write the failing tests**

> Review fix [C9]: SecretsStore is security-critical. Full test code required, not placeholders.

```python
# tests/unit/apollosai/storage/stores/test_secrets_store.py
"""Tests for ApollosAISecretsStore — encrypted secret storage.

Review fix [C9]: Full test implementations for security-critical encrypted storage.
Review fix [M14]: AAD mismatch tests for tenant isolation.
"""

import uuid

import pytest

from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
from openhands.storage.data_models.secrets import Secrets

# NOTE: async_session fixture from conftest.py (Task 4b)


class TestSecretsStoreLoad:
    @pytest.mark.asyncio
    async def test_load_returns_empty_when_no_session(self):
        """Backward compat: no DB session should return empty Secrets()."""
        store = ApollosAISecretsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None
        assert isinstance(result, Secrets)

    @pytest.mark.asyncio
    async def test_load_returns_empty_when_no_records(self, async_session, async_session_maker):
        """No DB records should return empty Secrets(), not None or error."""
        store = ApollosAISecretsStore(
            config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
        )
        result = await store.load()
        assert result is not None


class TestSecretsStoreRoundtrip:
    @pytest.mark.asyncio
    async def test_store_and_load_roundtrip(self, async_session, async_session_maker, monkeypatch):
        """Stored secrets should be retrievable via load()."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import reset_key_cache
        reset_key_cache()

        user_id = str(uuid.uuid4())
        org_id = uuid.uuid4()
        # Need user record with current_org_id for the store to resolve org context
        from apollosai.storage.models.user import User
        user = User(id=uuid.UUID(user_id), entra_oid='test', current_org_id=org_id)
        async_session.add(user)
        await async_session.commit()

        store = ApollosAISecretsStore(
            config=None, user_id=user_id, session_maker=async_session_maker
        )
        secrets = Secrets(llm_api_key='sk-test-key-12345')
        await store.store(secrets)

        loaded = await store.load()
        assert loaded.llm_api_key == 'sk-test-key-12345'

    @pytest.mark.asyncio
    async def test_store_upserts_existing_key(self, async_session, async_session_maker, monkeypatch):
        """Storing a secret for an existing key should update, not duplicate."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import reset_key_cache
        reset_key_cache()

        user_id = str(uuid.uuid4())
        org_id = uuid.uuid4()
        from apollosai.storage.models.user import User
        user = User(id=uuid.UUID(user_id), entra_oid='test', current_org_id=org_id)
        async_session.add(user)
        await async_session.commit()

        store = ApollosAISecretsStore(
            config=None, user_id=user_id, session_maker=async_session_maker
        )
        await store.store(Secrets(llm_api_key='key-v1'))
        await store.store(Secrets(llm_api_key='key-v2'))

        loaded = await store.load()
        assert loaded.llm_api_key == 'key-v2'


class TestSecretsStoreAAD:
    """Review fix [M14]: AAD-based tenant isolation."""

    def test_decrypt_with_wrong_aad_raises(self, monkeypatch):
        """Secrets encrypted with user_a:org_a must not decrypt with user_b:org_b."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value, reset_key_cache
        reset_key_cache()

        encrypted = encrypt_value('secret', aad='user1:org1')
        with pytest.raises(Exception):  # InvalidTag from cryptography
            decrypt_value(encrypted, aad='user2:org2')

    def test_encrypt_decrypt_with_aad_roundtrip(self, monkeypatch):
        """Matching AAD should decrypt successfully."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import decrypt_value, encrypt_value, reset_key_cache
        reset_key_cache()

        aad = 'user-uuid:org-uuid'
        encrypted = encrypt_value('my-api-key', aad=aad)
        assert decrypt_value(encrypted, aad=aad) == 'my-api-key'
```

**Step 2: Implement the store**

Update `apollosai/storage/stores/secrets_store.py` with:
- `load()`: Query `EncryptedSecret` by user_id + org_id, decrypt each value with `decrypt_value(value, aad=f"{user_id}:{org_id}")`
- `store()`: For each secret, `encrypt_value(value, aad=f"{user_id}:{org_id}")`, upsert to DB
- `get_instance()`: Use `get_session_maker()` from lifespan module [C1]

**Step 3: Run tests, commit**

```bash
git add apollosai/storage/stores/secrets_store.py tests/unit/apollosai/storage/stores/test_secrets_store.py
git commit -m "feat(apollosai): implement SecretsStore with AES-256-GCM encryption"
```

---

### Task 7: ConversationStore Implementation

**Files:**
- Modify: `apollosai/storage/stores/conversation_store.py`
- Modify: `tests/unit/apollosai/storage/stores/test_conversation_store.py`

**Step 1: Write the failing tests**

> Review fix [H11]: Full test implementations required, not comment-only.

```python
# tests/unit/apollosai/storage/stores/test_conversation_store.py
"""Tests for ApollosAIConversationStore — conversation metadata with soft delete."""

import uuid

import pytest

from apollosai.storage.stores.conversation_store import ApollosAIConversationStore

# NOTE: async_session fixture from conftest.py (Task 4b)


@pytest.mark.asyncio
async def test_save_and_get_metadata_roundtrip(async_session, async_session_maker):
    """Save then get should return matching conversation."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    from openhands.storage.data_models.conversation_metadata import ConversationMetadata
    meta = ConversationMetadata(conversation_id='conv-1', title='Test')
    await store.save_metadata(meta)
    loaded = await store.get_metadata('conv-1')
    assert loaded.conversation_id == 'conv-1'
    assert loaded.title == 'Test'


@pytest.mark.asyncio
async def test_get_metadata_validates_user_access(async_session, async_session_maker):
    """Review fix [M3]: Users should only access their own conversations.
    Use verified user_id from session, not from request params."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    store_a = ApollosAIConversationStore(
        config=None, user_id=user_a, session_maker=async_session_maker
    )
    from openhands.storage.data_models.conversation_metadata import ConversationMetadata
    await store_a.save_metadata(ConversationMetadata(conversation_id='conv-a', title='A'))

    store_b = ApollosAIConversationStore(
        config=None, user_id=user_b, session_maker=async_session_maker
    )
    with pytest.raises(FileNotFoundError):
        await store_b.get_metadata('conv-a')


@pytest.mark.asyncio
async def test_delete_metadata_sets_deleted_at(async_session, async_session_maker):
    """Soft delete should set deleted_at, not remove the row."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    from openhands.storage.data_models.conversation_metadata import ConversationMetadata
    await store.save_metadata(ConversationMetadata(conversation_id='conv-del', title='Del'))
    await store.delete_metadata('conv-del')
    assert not await store.exists('conv-del')


@pytest.mark.asyncio
async def test_exists_returns_false_for_soft_deleted(async_session, async_session_maker):
    """Review fix [M5]: exists() must exclude soft-deleted records."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    from openhands.storage.data_models.conversation_metadata import ConversationMetadata
    await store.save_metadata(ConversationMetadata(conversation_id='conv-sd', title='SD'))
    assert await store.exists('conv-sd')
    await store.delete_metadata('conv-sd')
    assert not await store.exists('conv-sd')


@pytest.mark.asyncio
async def test_search_filters_by_user(async_session, async_session_maker):
    """Search should only return conversations for the current user."""
    user_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    store = ApollosAIConversationStore(
        config=None, user_id=user_id, session_maker=async_session_maker
    )
    other_store = ApollosAIConversationStore(
        config=None, user_id=other_id, session_maker=async_session_maker
    )
    from openhands.storage.data_models.conversation_metadata import ConversationMetadata
    await store.save_metadata(ConversationMetadata(conversation_id='mine', title='Mine'))
    await other_store.save_metadata(ConversationMetadata(conversation_id='theirs', title='Theirs'))
    results = await store.search()
    assert len(results.results) == 1
    assert results.results[0].conversation_id == 'mine'


@pytest.mark.asyncio
async def test_search_returns_empty_for_new_user(async_session, async_session_maker):
    """New user with no conversations should get empty results."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    results = await store.search()
    assert len(results.results) == 0
```

**Step 2: Implement all 5 methods**

Use `Conversation` model. Each method:
- `save_metadata`: Create `Conversation` record from `ConversationMetadata`
- `get_metadata`: SELECT by id WHERE deleted_at IS NULL AND user_id matches (**Review fix [M3]:** use `self.user_id` from authenticated session, not from request params — prevents IDOR)
- `delete_metadata`: SET deleted_at = now()
- `exists`: SELECT EXISTS WHERE deleted_at IS NULL AND user_id matches
- `search`: SELECT with pagination via `page_id` (cursor-based, ordered by created_at DESC)
- `get_instance()`: Use `get_session_maker()` from lifespan module [C1]

**Step 3: Run tests, commit**

```bash
git add apollosai/storage/stores/conversation_store.py tests/unit/apollosai/storage/stores/test_conversation_store.py
git commit -m "feat(apollosai): implement ConversationStore with DB queries and soft delete"
```

---

## Layer 3: Auth Completion

### Task 8: User Upsert on Login

**Files:**
- Modify: `apollosai/server/routes/auth.py`
- Create: `apollosai/storage/services/user_service.py`
- Test: `tests/unit/apollosai/storage/services/test_user_service.py`
- Test: `tests/unit/apollosai/server/routes/test_auth.py` (modify existing)

**Step 1: Write the failing test for user_service**

```python
# tests/unit/apollosai/storage/services/test_user_service.py

@pytest.mark.asyncio
async def test_upsert_user_creates_new_user(async_session):
    """First login should create User + default Org + OrgMembership."""
    from apollosai.storage.services.user_service import upsert_user_on_login

    user = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='test@example.com',
        display_name='Test User',
    )
    assert user is not None
    assert user.entra_oid == 'test-oid-123'
    assert user.current_org_id is not None  # Default org created


@pytest.mark.asyncio
async def test_upsert_user_updates_existing(async_session):
    """Second login should update email, not create duplicate."""
    from apollosai.storage.services.user_service import upsert_user_on_login

    user1 = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='old@example.com',
        display_name='Test User',
    )
    user2 = await upsert_user_on_login(
        session=async_session,
        entra_oid='test-oid-123',
        email='new@example.com',
        display_name='Test User Updated',
    )
    assert user1.id == user2.id
    assert user2.email == 'new@example.com'
```

**Step 2: Implement user_service**

```python
# apollosai/storage/services/user_service.py
"""User lifecycle operations — upsert on login, default org creation."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.organization import Organization
from apollosai.storage.models.role import Role
from apollosai.storage.models.user import User


async def upsert_user_on_login(
    session: AsyncSession,
    entra_oid: str,
    email: str,
    display_name: str | None = None,
) -> User:
    """Create or update user on login. Creates default org on first login."""
    stmt = select(User).where(User.entra_oid == entra_oid)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if user is not None:
        # Existing user — update fields
        user.email = email
        if display_name:
            user.display_name = display_name
        await session.commit()
        return user

    # New user — create with default org
    # Review fix [C6]: Use UUID suffix to prevent org name collision DoS
    org = Organization(id=uuid.uuid4(), name=f'{email}-workspace-{uuid.uuid4().hex[:8]}')
    session.add(org)

    user = User(
        id=uuid.uuid4(),
        entra_oid=entra_oid,
        email=email,
        display_name=display_name,
        current_org_id=org.id,
    )
    session.add(user)

    # Get or create owner role
    # Review fix [M10]: Use INSERT ... ON CONFLICT DO NOTHING to avoid race
    # condition on concurrent first-logins. Better: pre-seed roles in Alembic migration.
    role_stmt = select(Role).where(Role.name == 'owner')
    role_result = await session.execute(role_stmt)
    owner_role = role_result.scalar_one_or_none()
    if owner_role is None:
        owner_role = Role(name='owner', rank=0)
        session.add(owner_role)
        await session.flush()

    # Add org membership
    membership = OrgMembership(
        org_id=org.id, user_id=user.id, role_id=owner_role.id
    )
    session.add(membership)
    await session.commit()
    return user
```

**Step 2b: Add OrgMembership verification test**

> Review fix [H3]: Must verify OrgMembership is created with owner role.

```python
@pytest.mark.asyncio
async def test_upsert_creates_org_membership_with_owner_role(async_session):
    """Review fix [H3]: User must get OrgMembership with owner role on first login."""
    from apollosai.storage.services.user_service import upsert_user_on_login

    user = await upsert_user_on_login(
        session=async_session, entra_oid='oid-1', email='test@example.com',
    )
    from sqlalchemy import select
    from apollosai.storage.models.org_membership import OrgMembership
    from apollosai.storage.models.role import Role

    stmt = select(OrgMembership).where(OrgMembership.user_id == user.id)
    result = await async_session.execute(stmt)
    membership = result.scalar_one()
    role = await async_session.get(Role, membership.role_id)
    assert role.name == 'owner'
```

**Step 3: Wire into auth callback**

Modify `apollosai/server/routes/auth.py` callback to call `upsert_user_on_login()` after MSAL token exchange, using the user's DB UUID as `sub` in the JWT instead of the raw Entra OID.

> **Review fix [C7]: JWT `sub` claim migration strategy.**
> Existing JWTs use Entra OID as `sub`. After this change, new JWTs use DB UUID.
> Strategy: Add `sub_type: 'db_uuid'` claim to new tokens. In `get_instance()`,
> check for `sub_type` — if absent, treat `sub` as Entra OID (legacy) and look up
> the DB user by `entra_oid` instead of by `id`. This provides backward compatibility
> during the transition period. After all active sessions expire (JWT TTL), remove
> the legacy path.

**Step 4: Run tests, commit**

```bash
git add apollosai/storage/services/__init__.py apollosai/storage/services/user_service.py \
    tests/unit/apollosai/storage/services/__init__.py tests/unit/apollosai/storage/services/test_user_service.py \
    apollosai/server/routes/auth.py tests/unit/apollosai/server/routes/test_auth.py
git commit -m "feat(apollosai): upsert user on login with default org creation"
```

---

### Task 9: Token Cache Persistence

**Files:**
- Modify: `apollosai/server/auth/msal_client.py`
- Create: `apollosai/storage/services/token_cache_service.py`
- Test: `tests/unit/apollosai/storage/services/test_token_cache_service.py`

**Key implementation:**
- `save_token_cache(session, user_id, cache)`: Serialize MSAL cache, encrypt with `encrypt_value(json, aad=str(user_id))`, upsert to `auth_token` table
- `load_token_cache(session, user_id)`: Load from `auth_token`, decrypt, deserialize to `SerializableTokenCache`
- Wire into `msal_client.py` `acquire_token_by_auth_code_flow()` to persist cache after token exchange
- Wire into `entraid_auth.py` `get_for_user()` to load cache for silent token refresh

**Step 1: Write tests**

> Review fix [H5]: Full test code required for token cache persistence.

```python
# tests/unit/apollosai/storage/services/test_token_cache_service.py

import uuid
import pytest


@pytest.mark.asyncio
async def test_save_and_load_token_cache_roundtrip(async_session, monkeypatch):
    """Token cache should survive encrypt -> store -> load -> decrypt."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache
    reset_key_cache()
    from apollosai.storage.services.token_cache_service import (
        load_token_cache, save_token_cache,
    )
    user_id = uuid.uuid4()
    await save_token_cache(async_session, user_id, '{"AccessToken": {"key": "value"}}')
    loaded = await load_token_cache(async_session, user_id)
    assert loaded == '{"AccessToken": {"key": "value"}}'


@pytest.mark.asyncio
async def test_load_nonexistent_cache_returns_none(async_session):
    """No cached token should return None, not raise."""
    from apollosai.storage.services.token_cache_service import load_token_cache
    result = await load_token_cache(async_session, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_save_overwrites_existing_cache(async_session, monkeypatch):
    """Second save should update, not create a duplicate."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache
    reset_key_cache()
    from apollosai.storage.services.token_cache_service import (
        load_token_cache, save_token_cache,
    )
    user_id = uuid.uuid4()
    await save_token_cache(async_session, user_id, '{"v": 1}')
    await save_token_cache(async_session, user_id, '{"v": 2}')
    loaded = await load_token_cache(async_session, user_id)
    assert '"v": 2' in loaded


@pytest.mark.asyncio
async def test_cache_encrypted_at_rest(async_session, monkeypatch):
    """Raw DB value should not equal plaintext (encryption verified)."""
    monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
    from apollosai.storage.encrypt_utils import reset_key_cache
    reset_key_cache()
    from apollosai.storage.services.token_cache_service import save_token_cache
    from apollosai.storage.models.auth_token import AuthToken
    user_id = uuid.uuid4()
    plaintext = '{"AccessToken": {"key": "secret"}}'
    await save_token_cache(async_session, user_id, plaintext)
    token = await async_session.get(AuthToken, user_id)
    assert token.token_cache != plaintext  # Must be encrypted
```

**Step 2: Implement, Step 3: Run tests, Step 4: Commit**

```bash
git commit -m "feat(apollosai): persist MSAL token cache with AES-256-GCM encryption"
```

---

### Task 10: API Key Authentication

**Files:**
- Create: `apollosai/server/routes/api_keys.py`
- Create: `apollosai/storage/services/api_key_service.py`
- Modify: `apollosai/server/auth/entraid_auth.py` (add API key path to `get_instance`)
- Modify: `apollosai/app_server.py` (mount route)
- Test: `tests/unit/apollosai/storage/services/test_api_key_service.py`
- Test: `tests/unit/apollosai/server/routes/test_api_keys.py`

**Key implementation:**

`api_key_service.py`:
- `create_api_key(session, user_id, org_id, name)`: Generate `sk-aai-{secrets.token_urlsafe(32)}`, store HMAC-SHA256 hash + salt + prefix
- `verify_api_key(session, raw_key)`: Extract prefix, lookup by prefix, verify HMAC. **Review fix [C3]: MUST use `hmac.compare_digest()` for ALL hash comparisons — never Python `==`.**
- `list_api_keys(session, user_id, org_id)`: Return prefix + name only
- `revoke_api_key(session, key_id, user_id)`: Set `is_active = False`

```python
# Key code in verify_api_key():
import hmac as hmac_mod
computed = hmac_mod.new(salt.encode(), raw_key.encode(), 'sha256').hexdigest()
if not hmac_mod.compare_digest(computed, stored_hash):
    raise InvalidTokenError('Invalid API key')
# Review fix [C3]: hmac.compare_digest() prevents timing attacks
```

`entraid_auth.py` `get_instance()` — add before JWT cookie check:
```python
# Check for API key (sk-aai-...) in Bearer header
# Review fix [H7]: Invalid API key MUST raise, not fall through to JWT
if token and token.startswith('sk-aai-'):
    user = await _verify_api_key(token)
    if user:
        return cls(user_id=str(user.id), email=user.email)
    raise InvalidTokenError('Invalid API key')
```

`api_keys.py` routes:
- `POST /api/keys` — Creates key, returns plaintext once
- `GET /api/keys` — Lists user's active keys (prefix + name)
- `DELETE /api/keys/{key_id}` — Revokes key

> Review fix [H2]: Add rate limiting on API key verification failures.
> Apply `@limiter.limit('20/minute')` on failed API key attempts per IP.
> Also rate limit `POST /api/keys` at 5/minute per user (already in design doc).

**Tests:**

```python
# tests/unit/apollosai/storage/services/test_api_key_service.py

import pytest

@pytest.mark.asyncio
async def test_create_and_verify_roundtrip(async_session):
    """Create key then verify it should succeed."""
    from apollosai.storage.services.api_key_service import create_api_key, verify_api_key
    raw_key, _ = await create_api_key(async_session, user_id=..., org_id=..., name='test')
    user = await verify_api_key(async_session, raw_key)
    assert user is not None

@pytest.mark.asyncio
async def test_revoked_key_verify_fails(async_session):
    """Revoked key (is_active=False) must not authenticate."""
    from apollosai.storage.services.api_key_service import (
        create_api_key, revoke_api_key, verify_api_key,
    )
    raw_key, key_record = await create_api_key(async_session, user_id=..., org_id=..., name='t')
    await revoke_api_key(async_session, key_record.id, user_id=...)
    result = await verify_api_key(async_session, raw_key)
    assert result is None

@pytest.mark.asyncio
async def test_verify_nonexistent_prefix_returns_none(async_session):
    """Prefix not in DB should return None, not raise."""
    from apollosai.storage.services.api_key_service import verify_api_key
    result = await verify_api_key(async_session, 'sk-aai-nonexistent')
    assert result is None

@pytest.mark.asyncio
async def test_two_keys_same_user_have_different_salts(async_session):
    """Review fix [C3-test]: Each key must have unique salt."""
    from apollosai.storage.services.api_key_service import create_api_key
    _, k1 = await create_api_key(async_session, user_id=..., org_id=..., name='k1')
    _, k2 = await create_api_key(async_session, user_id=..., org_id=..., name='k2')
    assert k1.salt != k2.salt

def test_verify_uses_timing_safe_comparison():
    """Review fix [C3-test]: HMAC comparison must use hmac.compare_digest."""
    import inspect
    from apollosai.storage.services.api_key_service import verify_api_key
    source = inspect.getsource(verify_api_key)
    assert 'compare_digest' in source, 'Must use hmac.compare_digest for timing safety'

# Integration tests in test_api_keys.py:
# - test_get_instance_from_api_key_bearer [H7-test]
# - test_api_key_auth_takes_priority_over_jwt [H7-test]
# - test_invalid_api_key_raises_not_falls_through [H7-test]
```

```bash
git commit -m "feat(apollosai): add API key CRUD routes and Bearer auth support"
```

---

## Layer 4: RBAC + Management Routes

### Task 11: RBAC Dependencies

**Files:**
- Create: `apollosai/server/auth/rbac.py`
- Test: `tests/unit/apollosai/server/auth/test_rbac.py`

**Key implementation:**

```python
# apollosai/server/auth/rbac.py
"""RBAC FastAPI dependencies for role-based access control.

Review fixes incorporated:
- [C2]: Wire session via Depends(get_db_session), NOT default None
- [C4]: Raise NoCredentialsError on missing user_id, never fabricate UUID
- [C5]: Add PermissionDeniedError to exception handlers in app_server.py
"""

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.auth_error import AuthError, NoCredentialsError
from apollosai.server.deps import get_db_session
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.role import Role


class PermissionDeniedError(AuthError):
    """User lacks required role for this operation."""
    pass


# Review fix [C4]: Well-known sentinel UUID for dev mode (APOLLOSAI_ALLOW_UNAUTHENTICATED)
DEV_MODE_USER_ID = uuid.UUID('00000000-0000-0000-0000-000000000000')


@dataclass
class AuthedUser:
    """Authenticated user with resolved role context."""
    user_id: uuid.UUID
    email: str | None
    org_id: uuid.UUID | None
    role_name: str | None
    role_rank: int | None


async def require_auth(request: Request) -> AuthedUser:
    """Validate JWT and return AuthedUser. Raises on failure."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = await EntraIDUserAuth.get_instance(request)
    # Review fix [C4]: Never fabricate random UUID. Use sentinel for dev mode.
    if not auth.user_id:
        import os
        if os.environ.get('APOLLOSAI_ALLOW_UNAUTHENTICATED', '').lower() in ('1', 'true', 'yes'):
            return AuthedUser(
                user_id=DEV_MODE_USER_ID, email='dev@localhost',
                org_id=None, role_name=None, role_rank=None,
            )
        raise NoCredentialsError('No user_id in auth context')
    return AuthedUser(
        user_id=uuid.UUID(auth.user_id),
        email=auth.email,
        org_id=None,
        role_name=None,
        role_rank=None,
    )


def require_role(min_role: str):
    """Dependency factory: require minimum role rank for org context."""
    ROLE_RANKS = {'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}

    async def _check(
        org_id: uuid.UUID,
        user: AuthedUser = Depends(require_auth),
        # Review fix [C2]: Wire via Depends(), NOT default None
        session: AsyncSession = Depends(get_db_session),
    ) -> AuthedUser:
        min_rank = ROLE_RANKS.get(min_role, 3)
        stmt = (
            select(OrgMembership, Role)
            .join(Role, OrgMembership.role_id == Role.id)
            .where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user.user_id,
            )
        )
        result = await session.execute(stmt)
        row = result.one_or_none()
        if row is None:
            raise PermissionDeniedError('Not a member of this organization')
        membership, role = row
        if role.rank > min_rank:
            raise PermissionDeniedError(
                f'Requires {min_role} role (rank {min_rank}), '
                f'you have {role.name} (rank {role.rank})'
            )
        user.org_id = org_id
        user.role_name = role.name
        user.role_rank = role.rank
        return user

    return _check
```

> **Review fix [C5]: Register exception handler in `app_server.py`:**
> ```python
> from apollosai.server.auth.rbac import PermissionDeniedError
>
> @base_app.exception_handler(PermissionDeniedError)
> async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
>     return JSONResponse(status_code=403, content={'error': str(exc)})
> ```

**Tests:** Full RBAC test suite per review findings [C4-test]:

```python
# tests/unit/apollosai/server/auth/test_rbac.py
"""RBAC dependency tests — review fix [C4-test]: comprehensive edge cases."""

import uuid
import pytest
from apollosai.server.auth.rbac import (
    AuthedUser, PermissionDeniedError, require_role, require_auth, DEV_MODE_USER_ID,
)

# Role hierarchy boundary tests
@pytest.mark.asyncio
async def test_owner_passes_admin_check(async_session):
    """rank 0 <= 1 should pass."""

@pytest.mark.asyncio
async def test_admin_passes_admin_check(async_session):
    """rank 1 <= 1 should pass."""

@pytest.mark.asyncio
async def test_manager_fails_admin_check(async_session):
    """rank 2 > 1 should raise PermissionDeniedError."""

@pytest.mark.asyncio
async def test_member_fails_admin_check(async_session):
    """rank 3 > 1 should raise PermissionDeniedError."""

# Edge cases
@pytest.mark.asyncio
async def test_non_member_raises_permission_denied(async_session):
    """User not in org should get PermissionDeniedError."""

@pytest.mark.asyncio
async def test_require_auth_with_no_user_id_raises(monkeypatch):
    """Review fix [C4]: Missing user_id should raise, not fabricate UUID."""

@pytest.mark.asyncio
async def test_require_auth_dev_mode_uses_sentinel(monkeypatch):
    """Review fix [C4]: Dev mode should use DEV_MODE_USER_ID, not random."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    # ... mock EntraIDUserAuth.get_instance to return auth with user_id=None
    # assert result.user_id == DEV_MODE_USER_ID

# Cross-org isolation
@pytest.mark.asyncio
async def test_user_in_org_a_cannot_access_org_b(async_session):
    """Review fix [C4-test]: Cross-org access must be denied."""

@pytest.mark.asyncio
async def test_require_role_with_null_session_raises(monkeypatch):
    """Review fix [C2]: If DI fails, should get clear error, not NoneType."""
```

```bash
git commit -m "feat(apollosai): add RBAC FastAPI dependencies with role hierarchy"
```

---

### Task 12: Organization CRUD Routes

**Files:**
- Create: `apollosai/server/routes/orgs.py`
- Create: `apollosai/server/routes/models.py` (Pydantic request/response models)
- Modify: `apollosai/app_server.py` (mount router)
- Test: `tests/unit/apollosai/server/routes/test_orgs.py`

**Key endpoints:** GET/POST/PATCH/DELETE `/api/orgs` and `/api/orgs/{id}/members`

> **Review fix [M1]: Input validation on org names.** Use Pydantic request models:
> ```python
> class CreateOrgRequest(BaseModel):
>     name: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9\s\-_]+$')
> ```

> **Review fix [H6]: Organization deletion must be soft-delete.**
> Add `deleted_at` column to Organization model (in Phase 2 migration).
> Hard deletion requires separate admin confirmation. Define FK cascade rules:
> - `OrgMembership`: CASCADE on org soft-delete (deactivate memberships)
> - `Team`: CASCADE soft-delete (teams inherit org deletion)
> - `User.current_org_id`: SET NULL on org deletion
> - `EncryptedSecret`, `Conversation`: Retain but inaccessible (filtered by active org)

**Tests:**

> Review fix [H4-test]: Full route tests required, not just endpoint references.

```python
# tests/unit/apollosai/server/routes/test_orgs.py

@pytest.mark.asyncio
async def test_create_org_sets_creator_as_owner(client, authed_user):
    """POST /api/orgs should make creator the owner."""

@pytest.mark.asyncio
async def test_update_org_as_admin_succeeds(client, admin_user):
    """PATCH /api/orgs/{id} with admin role should succeed."""

@pytest.mark.asyncio
async def test_update_org_as_member_returns_403(client, member_user):
    """PATCH /api/orgs/{id} with member role should return 403."""

@pytest.mark.asyncio
async def test_delete_org_requires_owner(client, admin_user):
    """DELETE /api/orgs/{id} as admin (not owner) should return 403."""

@pytest.mark.asyncio
async def test_invite_member_creates_org_membership(client, admin_user):
    """POST /api/orgs/{id}/members should create OrgMembership."""

@pytest.mark.asyncio
async def test_remove_self_as_last_owner_denied(client, owner_user):
    """Cannot remove the last owner from an org."""

@pytest.mark.asyncio
async def test_org_name_validation_rejects_special_chars(client, authed_user):
    """Review fix [M1]: Org names with XSS payloads should be rejected."""
    response = client.post('/api/orgs', json={'name': '<script>alert(1)</script>'})
    assert response.status_code == 422
```

```bash
git commit -m "feat(apollosai): add organization CRUD routes with RBAC"
```

---

### Task 13: Team CRUD Routes

**Files:**
- Create: `apollosai/server/routes/teams.py`
- Modify: `apollosai/app_server.py` (mount router)
- Test: `tests/unit/apollosai/server/routes/test_teams.py`

**Key endpoints:** GET/POST/PATCH/DELETE for teams and team members.

> Review fix [M1]: Apply same input validation pattern for team names.

**Tests:**

```python
# tests/unit/apollosai/server/routes/test_teams.py

@pytest.mark.asyncio
async def test_create_team_as_admin_succeeds(client, admin_user): ...

@pytest.mark.asyncio
async def test_create_team_as_member_returns_403(client, member_user): ...

@pytest.mark.asyncio
async def test_add_team_member_as_manager_succeeds(client, manager_user): ...

@pytest.mark.asyncio
async def test_delete_team_requires_admin(client, manager_user):
    """Manager can manage members but cannot delete the team."""
```

```bash
git commit -m "feat(apollosai): add team CRUD routes with RBAC"
```

---

## Layer 5: Security Hardening

### Task 14: JWT Revocation

**Files:**
- Modify: `apollosai/server/auth/jwt_utils.py` (add `jti` claim)
- Create: `apollosai/storage/services/token_revocation_service.py`
- Modify: `apollosai/server/routes/auth.py` (revoke on logout)
- Test: `tests/unit/apollosai/server/auth/test_jwt_utils.py` (modify existing)
- Test: `tests/unit/apollosai/storage/services/test_token_revocation.py`

**Key changes:**

> **Review fix [C10]: Integration point design.** `decode_session_token()` is a pure
> function (no DB access). Rather than making it async, split into two functions:
> 1. `decode_session_token()` — pure decode (unchanged), now adds `jti` to payload
> 2. `validate_session_token(token, session)` — decode + revocation check (NEW)
>
> All callers that need revocation protection must use `validate_session_token()`.
> The primary caller is `EntraIDUserAuth.get_instance()` (entraid_auth.py).

- `create_session_token()`: Add `jti: str(uuid.uuid4())` to payload
- `decode_session_token()`: Pure decode only (unchanged signature, backward compat)
- **NEW** `validate_session_token(token, session)`: Decode + check `jti` against `revoked_token` table. Raises `InvalidTokenError` if revoked.
- `revoke_token(session, jti, expires_at)`: Insert into `revoked_token`
- Logout handler: Extract `jti` from current token, revoke it

**Tests:**

```python
# Review fix [C10-test]: Test the integration point where revocation is checked.

@pytest.mark.asyncio
async def test_revoked_token_rejected_at_validation(async_session, monkeypatch):
    """A valid JWT with revoked jti must be rejected by validate_session_token."""
    from apollosai.server.auth.jwt_utils import create_session_token, validate_session_token
    from apollosai.storage.services.token_revocation_service import revoke_token
    import jwt

    token = create_session_token(user_id='u1', email='e@e.com', entra_oid='o1')
    payload = jwt.decode(token, options={'verify_signature': False})
    await revoke_token(async_session, payload['jti'], payload['exp'])
    with pytest.raises(Exception, match='revoked'):
        await validate_session_token(token, async_session)

@pytest.mark.asyncio
async def test_token_without_jti_still_works(async_session, monkeypatch):
    """Backward compat: existing tokens without jti should NOT break."""
    # Tokens issued before Phase 2 won't have jti — validate_session_token
    # should accept them (skip revocation check if jti is absent).
```

```bash
git commit -m "feat(apollosai): add JWT revocation with jti claim and validate_session_token"
```

---

### Task 15: Server-Side Sessions

**Files:**
- Create: `apollosai/server/middleware/db_session_middleware.py`
- Modify: `apollosai/app_server.py` (replace SessionMiddleware)
- Test: `tests/unit/apollosai/server/middleware/test_db_session_middleware.py`

**Key implementation:** Custom ASGI middleware that stores session data in `server_session` table instead of cookies. Thin cookie contains only `session_id`.

> **Review fix [H3]: Encryption key separation.** Use distinct HKDF `info` for sessions:
> `info=b'apollosai-session-encryption'` (vs existing `b'apollosai-field-encryption'`).
> This ensures a compromise of one derived key doesn't compromise the other.

> **Review fix [M5]: Automated session cleanup.** Add a probabilistic cleanup task:
> On each request, 1% chance of running `DELETE FROM server_session WHERE expires_at < now()`.
> Also clean `revoked_token` table in the same pass. Log cleanup count.
> For production with pg_cron available, document how to set up scheduled cleanup.

**Tests:**

> Review fix [M7-test]: Full session middleware tests required.

```python
# tests/unit/apollosai/server/middleware/test_db_session_middleware.py

@pytest.mark.asyncio
async def test_new_request_creates_session(): ...

@pytest.mark.asyncio
async def test_session_data_persists_across_requests(): ...

@pytest.mark.asyncio
async def test_expired_session_returns_empty(): ...

@pytest.mark.asyncio
async def test_session_cookie_is_httponly_secure(): ...

@pytest.mark.asyncio
async def test_invalid_session_id_returns_empty_session(): ...

@pytest.mark.asyncio
async def test_session_id_is_cryptographically_random():
    """Session IDs must use secrets.token_urlsafe, not predictable values."""
```

```bash
git commit -m "feat(apollosai): add DB-backed server-side session middleware"
```

---

### Task 16: Rate Limiting

**Files:**
- Modify: `apollosai/app_server.py`
- Modify: `apollosai/server/routes/auth.py`
- Test: `tests/unit/apollosai/server/routes/test_rate_limiting.py`

**Key implementation:** Add `slowapi` limiter to auth routes:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.get('/auth/login')
@limiter.limit('10/minute')
async def login(request: Request): ...
```

**Note:** Add `slowapi` to `pyproject.toml` dependencies first.

> **Review fix [M2]: Redis backend for production.** In-memory storage is bypassed
> in multi-instance deployments. Default to Redis if `REDIS_URL` is set:
> ```python
> import os
> from slowapi import Limiter
> storage_uri = os.environ.get('REDIS_URL')
> if not storage_uri:
>     import warnings
>     warnings.warn('Rate limiting uses in-memory storage — ineffective with multiple workers')
> limiter = Limiter(key_func=get_remote_address, storage_uri=storage_uri)
> ```

> **Review fix [H2]: Rate limit API key verification failures.**
> Add `@limiter.limit('20/minute')` on the API key verification failure path.

**Tests:**

> Review fix [H8-test]: Use `freezegun` for deterministic rate limit tests.

```python
# tests/unit/apollosai/server/routes/test_rate_limiting.py

@pytest.mark.asyncio
async def test_login_rate_limited_after_10_requests(client):
    """10 requests should succeed, 11th should return 429."""
    for _ in range(10):
        client.get('/auth/login')
    response = client.get('/auth/login')
    assert response.status_code == 429

@pytest.mark.asyncio
async def test_rate_limit_resets_after_window(client):
    """After the window expires, requests should succeed again."""
    # Use freezegun to advance time past the 1-minute window
```

```bash
git commit -m "feat(apollosai): add rate limiting on auth endpoints via slowapi"
```

---

### Task 17: MSAL Signout

**Files:**
- Modify: `apollosai/server/routes/auth.py` (logout endpoint)
- Modify: `tests/unit/apollosai/server/routes/test_auth.py`

> **Review fix [L1]: Task ordering.** This task MUST come after Task 15 (server-side
> sessions). If implemented before Task 15, the auth flow still uses cookie sessions
> and the session clearing logic won't match the new middleware.

**Key change:** After clearing session, redirect to Microsoft signout:

> **Review fix [M6]:** Return JSON with `signout_url` (not a redirect) so the
> frontend can handle the flow. Document expected frontend behavior: call logout API,
> then `window.location.href = signout_url`.

> **Review fix [L3]: Open redirect validation.** Validate `redirect_after_login` to
> ensure it's a relative path or matches the app domain:
> ```python
> from urllib.parse import urlparse
> parsed = urlparse(redirect_url)
> if parsed.netloc and parsed.netloc != request.url.netloc:
>     redirect_url = '/'  # Reject external redirects
> ```

```python
@router.post('/auth/logout')
async def logout(request: Request, response: Response):
    request.session.clear()
    response.delete_cookie(key=COOKIE_NAME)
    # Revoke JWT (Task 14)
    # Build Microsoft signout URL
    from apollosai.server.auth.constants import get_entra_tenant_id
    tenant = get_entra_tenant_id()
    redirect_uri = request.url_for('is_apollosai')
    signout_url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri={redirect_uri}'
    return {'status': 'logged_out', 'signout_url': signout_url}
```

**Tests:**

```python
# Review fix [M8-test]: Test signout URL construction.
def test_logout_returns_signout_url(client, monkeypatch):
    monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant')
    response = client.post('/auth/logout')
    data = response.json()
    assert 'signout_url' in data
    assert 'login.microsoftonline.com/test-tenant' in data['signout_url']
    assert 'post_logout_redirect_uri' in data['signout_url']
```

```bash
git commit -m "feat(apollosai): add MSAL signout on logout"
```

---

## Layer 6: Frontend Integration

### Task 18: Entra ID Login Button

**Files:**
- Modify: `frontend/src/components/features/auth/login-content.tsx`
- Create: `frontend/src/utils/generate-entra-auth-url.ts`
- Modify: `frontend/src/hooks/use-auth-callback.ts` (add ENTRA_ID)
- Modify: `frontend/src/hooks/use-auto-login.ts` (support entra_id)

**Key implementation:**
- `generateEntraAuthUrl()` returns `/api/auth/login?returnTo=${encodeURIComponent(returnUrl)}`
- Add `ENTRA_ID = 'entra_id'` to `LoginMethod` enum
- Login page: show "Sign in with Microsoft" when config indicates ApollosAI mode
- Auto-login hook supports `entra_id` provider

> **Review fix [L3]: Open redirect.** `generateEntraAuthUrl()` uses `window.location.href`
> as `returnTo`. Server-side validation (Task 17) prevents external redirects.

**Tests:**

> Review fix [M11]: Frontend utility must have vitest tests.

```typescript
// frontend/src/utils/__tests__/generate-entra-auth-url.test.ts
import { describe, it, expect } from 'vitest';
import { generateEntraAuthUrl } from '../generate-entra-auth-url';

describe('generateEntraAuthUrl', () => {
  it('returns login URL with encoded returnTo', () => {
    const url = generateEntraAuthUrl('/conversations');
    expect(url).toBe('/api/auth/login?returnTo=%2Fconversations');
  });

  it('handles special characters in returnTo', () => {
    const url = generateEntraAuthUrl('/path?foo=bar&baz=1');
    expect(url).toContain('returnTo=');
    expect(url).not.toContain('&baz='); // Should be encoded
  });
});
```

```bash
git commit -m "feat(frontend): add Entra ID login button and auth URL generation"
```

---

### Task 19: Org/Team API Service & Hooks

**Files:**
- Create: `frontend/src/api/org-service/org-service.api.ts`
- Create: `frontend/src/hooks/query/use-organizations.ts`
- Create: `frontend/src/hooks/query/use-teams.ts`
- Create: `frontend/src/hooks/mutation/use-switch-org.ts`
- Create: `frontend/src/hooks/mutation/use-switch-team.ts`

**Key implementation:**
- `OrgService` with methods matching the `/api/orgs` and `/api/teams` endpoints
- Query hooks use TanStack Query with appropriate staleTime
- Mutation hooks invalidate settings/secrets queries on org/team switch

**Tests:**

> Review fix [L6]: Frontend hooks and service must have vitest tests.

```typescript
// frontend/src/hooks/query/__tests__/use-organizations.test.ts
describe('useOrganizations', () => {
  it('fetches org list from /api/orgs', () => { /* ... */ });
});

// frontend/src/hooks/mutation/__tests__/use-switch-org.test.ts
describe('useSwitchOrg', () => {
  it('invalidates settings queries after switch', () => { /* ... */ });
});
```

```bash
git commit -m "feat(frontend): add org/team API service and TanStack Query hooks"
```

---

### Task 20: Org/Team Selector Components

**Files:**
- Create: `frontend/src/components/features/workspace/org-selector.tsx`
- Create: `frontend/src/components/features/workspace/team-selector.tsx`
- Modify: `frontend/src/routes/root-layout.tsx` (integrate selectors)

**Key implementation:**
- `OrgSelector`: Dropdown using `useOrganizations()`, calls `useSwitchOrg()` on change
- `TeamSelector`: Dropdown using `useTeams(currentOrgId)`, calls `useSwitchTeam()` on change
- Both components placed in sidebar header area
- Switching invalidates relevant queries

**Tests:**

> Review fix [L6]: Component rendering tests.

```typescript
// frontend/src/components/features/workspace/__tests__/org-selector.test.tsx
describe('OrgSelector', () => {
  it('renders dropdown with org list', () => { /* renderWithProviders */ });
  it('calls switchOrg on selection change', () => { /* ... */ });
});
```

```bash
git commit -m "feat(frontend): add org/team selector components in sidebar"
```

---

## Final: Verification

### Task 21: Full Test Suite & Lint

**Step 1: Run all backend tests**

```bash
poetry run pytest tests/unit/apollosai/ -v --tb=short
```
Expected: All tests PASS

**Step 2: Run backend linting**

```bash
pre-commit run --all-files --show-diff-on-failure --config ./dev_config/python/.pre-commit-config.yaml
```
Expected: All hooks PASS

**Step 3: Run frontend tests**

```bash
cd frontend && npm run test
```
Expected: All tests PASS

**Step 4: Run frontend lint + build**

```bash
cd frontend && npm run lint:fix && npm run build
```
Expected: Clean build

**Step 5: Final commit if any lint fixes**

```bash
git add -A && git commit -m "chore(apollosai): Phase 2 lint fixes"
```

---

## Task Dependency Graph

```
Task 1 (DbSessionInjector) ─┐
Task 2 (Lifespan wiring) ───┤
Task 3 (Cleanup migration) ─┘
         │
Task 4 (Phase 2 models + migration)
         │
    ┌────┴────┐────────────┐
Task 5     Task 6        Task 7
(Settings) (Secrets)     (Conversations)
    └────┬────┘────────────┘
         │
    ┌────┴────┐
Task 8     Task 9
(Upsert)   (TokenCache)
    └────┬────┘
         │
Task 10 (API Keys)
         │
Task 11 (RBAC deps)
         │
    ┌────┴────┐
Task 12    Task 13
(Org CRUD) (Team CRUD)
    └────┬────┘
         │
    ┌────┴──────┬──────────┬────────┐
Task 14     Task 15     Task 16   Task 17
(JWT revoke)(Sessions)  (Rate lim)(MSAL out)
    └────┬──────┴──────────┴────────┘
         │
Task 18 (Login button)
         │
Task 19 (API + hooks)
         │
Task 20 (Selectors)
         │
Task 21 (Verification)
```

## Summary

- **21 tasks** across 6 layers
- **~14 new files**, ~13 modified files
- **Backend-first** (Tasks 1-17), then frontend (Tasks 18-20)
- **TDD throughout**: write test → verify fail → implement → verify pass → commit
- **1 new dependency**: `slowapi` (rate limiting)
- Estimated: ~20 commits across the implementation

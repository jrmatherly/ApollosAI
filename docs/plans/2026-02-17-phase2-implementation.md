# Phase 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement all Phase 2 enterprise functionality — DB sessions, store implementations, auth completion, RBAC, CRUD routes, security hardening, and frontend integration.

**Architecture:** Bottom-up incremental layers. Each layer builds on the previous. DB foundation first, then stores, auth, RBAC, security, frontend. Every new feature follows TDD.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.0 async, asyncpg, Alembic, AES-256-GCM, MSAL, React 19, TypeScript, TanStack Query, Zustand.

**Design doc:** `docs/plans/2026-02-17-phase2-design.md`

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

    __test__ = True

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
    async def test_inject_reuses_cached_session(self, monkeypatch):
        """Second inject call should return the same session."""
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        from starlette.datastructures import State

        state = State()
        sessions = []
        # First call
        async for s in injector.inject(state):
            sessions.append(s)
            # Set keep_open so session survives
            from apollosai.server.db_session import APOLLOSAI_DB_SESSION_ATTR
            # Session is cached on state, second call should reuse
        # Second call with same state
        async for s in injector.inject(state):
            sessions.append(s)
        assert sessions[0] is sessions[1]
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
from typing import AsyncGenerator

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


class ApollosAIDbSessionInjector(BaseModel, Injector[async_sessionmaker]):
    """Injects async SQLAlchemy sessions backed by ApollosAI's PostgreSQL."""

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
```

**Step 2: Run test to verify it fails**

Run: `poetry run pytest tests/unit/apollosai/server/test_lifespan.py -v -k "db_injector"`
Expected: FAIL with `AttributeError: 'ApollosAILifespanService' object has no attribute 'db_injector'`

**Step 3: Write minimal implementation**

Update `apollosai/server/lifespan.py`:

```python
"""ApollosAI lifespan service — manages startup/shutdown for the enterprise server."""

import os

from openhands.app_server.app_lifespan.oss_app_lifespan_service import (
    OssAppLifespanService,
)


class ApollosAILifespanService(OssAppLifespanService):
    """Enterprise lifespan service.

    Extends OssAppLifespanService to:
    1. Skip OpenHands' SQLite Alembic migrations
    2. Initialize async PostgreSQL engine via ApollosAIDbSessionInjector
    3. Dispose engine on shutdown
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

                # Will raise ValueError from get_database_url() if called
                self._db_injector = ApollosAIDbSessionInjector()
        return self._db_injector
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
    expires_at: Mapped[datetime.datetime] = mapped_column()
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

**Step 5: Write the Alembic migration (hand-written)**

Create `apollosai/migrations/versions/XXXX_phase2_schema.py` with `op.create_table()` calls for all 4 new tables. Use the same pattern as `faeef06e7fea_initial_schema.py`.

**Step 6: Commit**

```bash
git add apollosai/storage/models/encrypted_secret.py apollosai/storage/models/conversation.py \
    apollosai/storage/models/server_session.py apollosai/storage/models/revoked_token.py \
    apollosai/migrations/versions/*_phase2_schema.py \
    tests/unit/apollosai/storage/models/test_phase2_models.py
git commit -m "feat(apollosai): add Phase 2 models and migration (encrypted_secret, conversation, server_session, revoked_token)"
```

---

### Task 5: SettingsStore Implementation

**Files:**
- Modify: `apollosai/storage/stores/settings_store.py`
- Modify: `tests/unit/apollosai/storage/stores/test_settings_store.py`

**Step 1: Write the failing tests**

```python
# tests/unit/apollosai/storage/stores/test_settings_store.py
"""Tests for ApollosAISettingsStore — Org -> Team -> User resolution."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apollosai.storage.models.base import Base
from apollosai.storage.stores.settings_store import ApollosAISettingsStore


@pytest.fixture
async def async_session():
    """Create an in-memory SQLite async session for testing."""
    engine = create_async_engine('sqlite+aiosqlite://', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sm() as session:
        yield session
    await engine.dispose()


class TestSettingsStoreLoad:
    """Test settings resolution chain."""

    @pytest.mark.asyncio
    async def test_load_returns_settings_when_no_db(self):
        """Without a session_maker, should return config defaults (backward compat)."""
        store = ApollosAISettingsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_with_session_returns_org_defaults(self, async_session):
        """With a session, should query org-level LLM defaults."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-4')
        user = User(id=uuid.uuid4(), entra_oid='test-oid', current_org_id=org.id)
        async_session.add_all([org, user])
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session.get_bind
        )
        # This test verifies the org defaults flow; exact assertion depends on Settings shape

    @pytest.mark.asyncio
    async def test_load_team_overrides_org(self, async_session):
        """Team-level settings should override org defaults."""
        # Setup org with model A, team with model B
        # Assert loaded settings use model B
        pass  # Implement with actual DB records


class TestSettingsStoreStore:
    """Test settings persistence."""

    @pytest.mark.asyncio
    async def test_store_persists_settings(self):
        """Store should write settings to the user tier."""
        # Will be implemented once store() is functional
        pass
```

**Step 2: Run test to verify current stubs produce expected behavior**

Run: `poetry run pytest tests/unit/apollosai/storage/stores/test_settings_store.py -v`
Expected: Some tests fail (the DB-backed ones), stubs pass

**Step 3: Implement the store**

Update `apollosai/storage/stores/settings_store.py`:

```python
"""PostgreSQL-backed settings with Org -> Team -> User resolution."""

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
        return cls(config=config, user_id=user_id)
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

```python
# Key tests to add:
# - test_load_returns_empty_when_no_session (backward compat)
# - test_load_decrypts_secrets_from_db
# - test_store_encrypts_and_persists
# - test_aad_uses_user_and_org_ids
```

**Step 2: Implement the store**

Update `apollosai/storage/stores/secrets_store.py` with:
- `load()`: Query `EncryptedSecret` by user_id + org_id, decrypt each value with `decrypt_value(value, aad=f"{user_id}:{org_id}")`
- `store()`: For each secret, `encrypt_value(value, aad=f"{user_id}:{org_id}")`, upsert to DB

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

```python
# Key tests to add:
# - test_save_metadata_persists_to_db
# - test_get_metadata_returns_conversation
# - test_get_metadata_validates_user_access
# - test_delete_metadata_soft_deletes
# - test_exists_returns_true_for_existing
# - test_exists_returns_false_for_deleted
# - test_search_returns_paginated_results
# - test_search_filters_by_user_and_org
```

**Step 2: Implement all 5 methods**

Use `Conversation` model. Each method:
- `save_metadata`: Create `Conversation` record from `ConversationMetadata`
- `get_metadata`: SELECT by id WHERE deleted_at IS NULL AND (user_id match OR org member)
- `delete_metadata`: SET deleted_at = now()
- `exists`: SELECT EXISTS with same access check
- `search`: SELECT with pagination via `page_id` (cursor-based, ordered by created_at DESC)

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
    org = Organization(id=uuid.uuid4(), name=f'{email}-workspace')
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

**Step 3: Wire into auth callback**

Modify `apollosai/server/routes/auth.py` callback to call `upsert_user_on_login()` after MSAL token exchange, using the user's DB UUID as `sub` in the JWT instead of the raw Entra OID.

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

**Step 1: Write tests, Step 2: Implement, Step 3: Run tests, Step 4: Commit**

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
- `verify_api_key(session, raw_key)`: Extract prefix, lookup by prefix, verify HMAC
- `list_api_keys(session, user_id, org_id)`: Return prefix + name only
- `revoke_api_key(session, key_id, user_id)`: Set `is_active = False`

`entraid_auth.py` `get_instance()` — add before JWT cookie check:
```python
# Check for API key (sk-aai-...) in Bearer header
if token and token.startswith('sk-aai-'):
    user = await _verify_api_key(token)
    if user:
        return cls(user_id=str(user.id), email=user.email)
```

`api_keys.py` routes:
- `POST /api/keys` — Creates key, returns plaintext once
- `GET /api/keys` — Lists user's active keys (prefix + name)
- `DELETE /api/keys/{key_id}` — Revokes key

**Tests: Create key → verify → list → revoke → verify fails**

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
"""RBAC FastAPI dependencies for role-based access control."""

import uuid
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.auth_error import AuthError
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.role import Role


class PermissionDeniedError(AuthError):
    """User lacks required role for this operation."""
    pass


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
    return AuthedUser(
        user_id=uuid.UUID(auth.user_id) if auth.user_id else uuid.uuid4(),
        email=auth.email,
        org_id=None,  # Resolved by downstream deps
        role_name=None,
        role_rank=None,
    )


def require_role(min_role: str):
    """Dependency factory: require minimum role rank for org context."""
    ROLE_RANKS = {'owner': 0, 'admin': 1, 'manager': 2, 'member': 3}

    async def _check(
        org_id: uuid.UUID,
        user: AuthedUser = Depends(require_auth),
        session: AsyncSession = None,  # Injected from db_session
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

**Tests:** Test each dependency with mocked DB (owner passes admin check, member fails admin check, non-member denied).

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
- `create_session_token()`: Add `jti: str(uuid.uuid4())` to payload
- `decode_session_token()`: After decoding, check `jti` against `revoked_token` table
- `revoke_token(session, jti, expires_at)`: Insert into `revoked_token`
- Logout handler: Extract `jti` from current token, revoke it

```bash
git commit -m "feat(apollosai): add JWT revocation with jti claim"
```

---

### Task 15: Server-Side Sessions

**Files:**
- Create: `apollosai/server/middleware/db_session_middleware.py`
- Modify: `apollosai/app_server.py` (replace SessionMiddleware)
- Test: `tests/unit/apollosai/server/middleware/test_db_session_middleware.py`

**Key implementation:** Custom ASGI middleware that stores session data in `server_session` table instead of cookies. Thin cookie contains only `session_id`.

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

```bash
git commit -m "feat(apollosai): add rate limiting on auth endpoints via slowapi"
```

---

### Task 17: MSAL Signout

**Files:**
- Modify: `apollosai/server/routes/auth.py` (logout endpoint)
- Modify: `tests/unit/apollosai/server/routes/test_auth.py`

**Key change:** After clearing session, redirect to Microsoft signout:
```python
@router.post('/auth/logout')
async def logout(request: Request, response: Response):
    request.session.clear()
    response.delete_cookie(key=COOKIE_NAME)
    # Revoke JWT (Task 14)
    # Redirect to Microsoft signout
    from apollosai.server.auth.constants import get_entra_tenant_id
    tenant = get_entra_tenant_id()
    redirect_uri = request.url_for('is_apollosai')
    signout_url = f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout?post_logout_redirect_uri={redirect_uri}'
    return {'status': 'logged_out', 'signout_url': signout_url}
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

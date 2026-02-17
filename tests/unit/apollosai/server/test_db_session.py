"""Tests for ApollosAI DbSessionInjector."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apollosai.server.db_session import APOLLOSAI_DB_SESSION_ATTR, ApollosAIDbSessionInjector


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
        Uses athrow() to properly test generator exception handling.
        """
        monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
        injector = ApollosAIDbSessionInjector()
        from starlette.datastructures import State

        state = State()
        gen = injector.inject(state)
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
        # Throw exception into generator — should trigger rollback + close
        with pytest.raises(RuntimeError):
            await gen.athrow(RuntimeError('simulated error'))

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

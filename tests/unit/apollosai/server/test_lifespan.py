"""Tests for ApollosAI lifespan service."""

import pytest

from apollosai.server.lifespan import ApollosAILifespanService
from openhands.app_server.app_lifespan.app_lifespan_service import AppLifespanService


def test_is_subclass():
    assert issubclass(ApollosAILifespanService, AppLifespanService)


def test_does_not_run_openhands_migrations():
    """ApollosAI has its own Alembic chain — must not run OpenHands migrations."""
    service = ApollosAILifespanService()
    assert service.run_alembic_on_startup is False


def test_has_async_context_manager_protocol():
    """Must support async with for lifespan management."""
    service = ApollosAILifespanService()
    assert hasattr(service, '__aenter__')
    assert hasattr(service, '__aexit__')


@pytest.mark.asyncio
async def test_lifespan_initializes_db_injector(monkeypatch):
    """Lifespan should initialize the DbSessionInjector on enter."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    service = ApollosAILifespanService()
    assert service.db_injector is not None


@pytest.mark.asyncio
async def test_lifespan_exposes_session_maker(monkeypatch):
    """Lifespan should store db_injector for use by stores."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    service = ApollosAILifespanService()
    assert service.db_injector is not None


@pytest.mark.asyncio
async def test_lifespan_enter_exit_lifecycle(monkeypatch):
    """Review fix [H1+M3-test]: Engine should init on enter, dispose on exit.

    Without __aenter__/__aexit__, engine leaks connections on every restart.
    """
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
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
    from apollosai.server.lifespan import get_session_maker

    service = ApollosAILifespanService()
    async with service:
        sm = get_session_maker()
        assert sm is not None


@pytest.mark.asyncio
async def test_module_level_session_maker_cleared_after_exit(monkeypatch):
    """After lifespan exits, get_session_maker() should return None."""
    monkeypatch.setenv('DATABASE_URL', 'sqlite+aiosqlite://')
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    from apollosai.server.lifespan import get_session_maker

    service = ApollosAILifespanService()
    async with service:
        pass  # Enter and exit
    assert get_session_maker() is None

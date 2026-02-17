import pytest

from apollosai.storage.database import (
    create_async_engine_from_url,
    create_session_factory,
    get_database_url,
)


def test_get_database_url_from_env(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+asyncpg://user:pass@localhost/db')
    assert get_database_url() == 'postgresql+asyncpg://user:pass@localhost/db'


def test_get_database_url_fixes_scheme(monkeypatch):
    """postgres:// should be rewritten to postgresql+asyncpg:// for async driver."""
    monkeypatch.setenv('DATABASE_URL', 'postgres://user:pass@localhost/db')
    assert get_database_url().startswith('postgresql+asyncpg://')


def test_get_database_url_missing_raises(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(ValueError, match='DATABASE_URL'):
        get_database_url()


def test_get_database_url_fixes_postgresql_scheme(monkeypatch):
    """postgresql:// (without +asyncpg) should also be rewritten."""
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')
    assert get_database_url().startswith('postgresql+asyncpg://')


def test_create_async_engine_returns_engine():
    """Verify engine creation doesn't fail (no actual DB connection yet)."""
    url = 'postgresql+asyncpg://user:pass@localhost:5432/test'
    engine = create_async_engine_from_url(url)
    assert engine is not None
    # SQLAlchemy 2.0 redacts passwords in str(url) by default
    assert 'localhost' in str(engine.url)


def test_create_session_factory():
    """Verify session factory can be created from an engine."""
    url = 'postgresql+asyncpg://user:pass@localhost:5432/test'
    engine = create_async_engine_from_url(url)
    factory = create_session_factory(engine)
    assert factory is not None

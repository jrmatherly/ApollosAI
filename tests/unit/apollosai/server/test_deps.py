"""Tests for FastAPI dependency functions."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

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
    monkeypatch.setattr(
        'apollosai.server.deps.get_session_maker', lambda: async_session_maker
    )
    async for session in get_db_session():
        assert session is not None
        assert isinstance(session, AsyncSession)

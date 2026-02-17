"""Tests for EntraIDUserContext and EntraIDUserContextInjector.

Verifies the V1 UserContext bridge follows the same patterns as
AuthUserContext/AuthUserContextInjector in auth_user_context.py.
"""

from unittest.mock import MagicMock

import pytest
from starlette.datastructures import State

from apollosai.server.auth.user_context import (
    EntraIDUserContext,
    EntraIDUserContextInjector,
)
from openhands.app_server.user.user_context import UserContext, UserContextInjector


def test_user_context_is_subclass():
    """EntraIDUserContext must extend the V1 UserContext ABC."""
    assert issubclass(EntraIDUserContext, UserContext)


def test_injector_is_subclass():
    """EntraIDUserContextInjector must extend UserContextInjector (Pydantic + Injector)."""
    assert issubclass(EntraIDUserContextInjector, UserContextInjector)


def test_user_context_has_required_methods():
    """All abstract methods from UserContext ABC must be implemented."""
    methods = [
        'get_user_id',
        'get_user_info',
        'get_authenticated_git_url',
        'get_provider_tokens',
        'get_latest_token',
        'get_secrets',
        'get_mcp_api_key',
    ]
    for method in methods:
        assert hasattr(EntraIDUserContext, method), f'Missing method: {method}'


@pytest.mark.asyncio
async def test_injector_produces_user_context(monkeypatch):
    """Core test: inject() must yield a working EntraIDUserContext."""
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')

    from apollosai.server.auth.jwt_utils import create_session_token

    token = create_session_token(
        user_id='user-1',
        email='test@example.com',
        entra_oid='oid-1',
    )
    request = MagicMock()
    request.cookies = {'session': token}
    request.headers = {}

    injector = EntraIDUserContextInjector()
    state = State()

    async for ctx in injector.inject(state, request):
        assert isinstance(ctx, EntraIDUserContext)
        assert await ctx.get_user_id() == 'user-1'


@pytest.mark.asyncio
async def test_injector_caches_context(monkeypatch):
    """Second call to inject() should return cached context from state."""
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')

    from apollosai.server.auth.jwt_utils import create_session_token

    token = create_session_token(
        user_id='user-2',
        email='test2@example.com',
        entra_oid='oid-2',
    )
    request = MagicMock()
    request.cookies = {'session': token}
    request.headers = {}

    injector = EntraIDUserContextInjector()
    state = State()

    # First call
    ctx1 = None
    async for ctx in injector.inject(state, request):
        ctx1 = ctx

    # Second call -- should return same cached context
    async for ctx2 in injector.inject(state, request):
        assert ctx1 is ctx2


@pytest.mark.asyncio
async def test_injector_raises_without_request(monkeypatch):
    """inject() with request=None must raise AuthError."""
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')

    from apollosai.server.auth.auth_error import AuthError

    injector = EntraIDUserContextInjector()
    state = State()

    with pytest.raises(AuthError, match='Request required'):
        async for _ in injector.inject(state, None):
            pass


@pytest.mark.asyncio
async def test_user_context_get_provider_tokens():
    """get_provider_tokens delegates to user_auth."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = EntraIDUserAuth(user_id='user-1', email='test@example.com')
    ctx = EntraIDUserContext(user_auth=auth)
    result = await ctx.get_provider_tokens()
    assert result is None


@pytest.mark.asyncio
async def test_user_context_get_secrets_empty():
    """get_secrets returns empty dict when user_auth has no secrets store."""
    from unittest.mock import AsyncMock

    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = EntraIDUserAuth(user_id='user-1', email='test@example.com')
    # Mock get_secrets to return None (no secrets store configured)
    auth.get_secrets = AsyncMock(return_value=None)
    ctx = EntraIDUserContext(user_auth=auth)
    result = await ctx.get_secrets()
    assert result == {}


@pytest.mark.asyncio
async def test_user_context_get_mcp_api_key():
    """get_mcp_api_key delegates to user_auth."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = EntraIDUserAuth(user_id='user-1', email='test@example.com')
    ctx = EntraIDUserContext(user_auth=auth)
    result = await ctx.get_mcp_api_key()
    assert result is None


@pytest.mark.asyncio
async def test_user_context_get_authenticated_git_url():
    """get_authenticated_git_url returns the repository URL as-is (Phase 2 TODO)."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = EntraIDUserAuth(user_id='user-1', email='test@example.com')
    ctx = EntraIDUserContext(user_auth=auth)
    result = await ctx.get_authenticated_git_url('owner/repo')
    assert result == 'owner/repo'


@pytest.mark.asyncio
async def test_user_context_get_latest_token():
    """get_latest_token returns None (Phase 2 TODO)."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth
    from openhands.integrations.provider import ProviderType

    auth = EntraIDUserAuth(user_id='user-1', email='test@example.com')
    ctx = EntraIDUserContext(user_auth=auth)
    result = await ctx.get_latest_token(ProviderType.GITHUB)
    assert result is None

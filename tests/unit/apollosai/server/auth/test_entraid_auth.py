import pytest

from apollosai.server.auth.entraid_auth import EntraIDUserAuth
from openhands.server.user_auth.user_auth import UserAuth


def test_is_subclass_of_user_auth():
    assert issubclass(EntraIDUserAuth, UserAuth)


@pytest.mark.asyncio
async def test_get_user_id():
    auth = EntraIDUserAuth(user_id='test-oid-123', email='test@example.com')
    result = await auth.get_user_id()
    assert result == 'test-oid-123'


@pytest.mark.asyncio
async def test_get_user_email():
    auth = EntraIDUserAuth(user_id='test-oid-123', email='test@example.com')
    result = await auth.get_user_email()
    assert result == 'test@example.com'


@pytest.mark.asyncio
async def test_get_access_token_none_when_no_token():
    auth = EntraIDUserAuth(user_id='test-oid-123', email=None)
    result = await auth.get_access_token()
    assert result is None


@pytest.mark.asyncio
async def test_get_provider_tokens_none():
    auth = EntraIDUserAuth(user_id='test-oid-123', email=None)
    result = await auth.get_provider_tokens()
    assert result is None


@pytest.mark.asyncio
async def test_get_instance_raises_without_env_guard(monkeypatch):
    """get_instance must raise NoCredentialsError unless APOLLOSAI_ALLOW_UNAUTHENTICATED is set."""
    from unittest.mock import AsyncMock

    from apollosai.server.auth.auth_error import NoCredentialsError

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    request = AsyncMock()
    with pytest.raises(NoCredentialsError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_get_instance_allows_with_env_guard(monkeypatch):
    """get_instance returns unauthenticated instance when env guard is set."""
    from unittest.mock import AsyncMock

    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    request = AsyncMock()
    auth = await EntraIDUserAuth.get_instance(request)
    assert isinstance(auth, EntraIDUserAuth)
    assert await auth.get_user_id() is None

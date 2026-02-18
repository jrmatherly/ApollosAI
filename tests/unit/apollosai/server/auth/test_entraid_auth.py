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


@pytest.fixture
def _set_jwt_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', 'test-jwt-secret-must-be-long-enough-32!')


def _make_mock_request(cookies=None, headers=None):
    """Create a mock request with dict-like cookies and headers."""
    from unittest.mock import MagicMock

    request = MagicMock()
    request.cookies = cookies or {}
    request.headers = headers or {}
    return request


@pytest.mark.asyncio
async def test_get_instance_raises_without_env_guard(monkeypatch, _set_jwt_secret):
    """get_instance must raise NoCredentialsError unless APOLLOSAI_ALLOW_UNAUTHENTICATED is set."""
    from apollosai.server.auth.auth_error import NoCredentialsError

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    request = _make_mock_request()
    with pytest.raises(NoCredentialsError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_get_instance_allows_with_env_guard(monkeypatch, _set_jwt_secret):
    """get_instance returns unauthenticated instance when env guard is set."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    request = _make_mock_request()
    auth = await EntraIDUserAuth.get_instance(request)
    assert isinstance(auth, EntraIDUserAuth)
    assert await auth.get_user_id() is None


@pytest.mark.asyncio
async def test_get_instance_from_jwt_cookie(monkeypatch, _set_jwt_secret):
    """get_instance extracts user from JWT cookie."""
    from apollosai.server.auth.jwt_utils import create_session_token

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    token = create_session_token(
        user_id='user-uuid-123',
        email='test@example.com',
        entra_oid='oid-456',
    )
    request = _make_mock_request(cookies={'apollosai_auth': token})

    auth = await EntraIDUserAuth.get_instance(request)
    assert await auth.get_user_id() == 'user-uuid-123'
    assert await auth.get_user_email() == 'test@example.com'


@pytest.mark.asyncio
async def test_get_instance_from_bearer_header(monkeypatch, _set_jwt_secret):
    """get_instance extracts user from Bearer JWT in Authorization header."""
    from apollosai.server.auth.jwt_utils import create_session_token

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    token = create_session_token(
        user_id='user-uuid-789',
        email='api@example.com',
        entra_oid='oid-012',
    )
    request = _make_mock_request(
        cookies={},
        headers={'authorization': f'Bearer {token}'},
    )

    auth = await EntraIDUserAuth.get_instance(request)
    assert await auth.get_user_id() == 'user-uuid-789'


@pytest.mark.asyncio
async def test_get_instance_invalid_token_raises(monkeypatch, _set_jwt_secret):
    """SECURITY: Invalid/expired token must hard-fail, never fall through."""
    from apollosai.server.auth.auth_error import InvalidTokenError

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    request = _make_mock_request(cookies={'apollosai_auth': 'invalid-jwt-token'})

    with pytest.raises(InvalidTokenError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_get_instance_invalid_token_does_not_fallthrough(
    monkeypatch, _set_jwt_secret
):
    """SECURITY: Even with ALLOW_UNAUTHENTICATED set, an invalid token must fail."""
    from apollosai.server.auth.auth_error import InvalidTokenError

    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    request = _make_mock_request(cookies={'apollosai_auth': 'forged-jwt'})

    with pytest.raises(InvalidTokenError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_get_instance_no_credentials_raises(monkeypatch, _set_jwt_secret):
    """get_instance raises NoCredentialsError when no cookie or header."""
    from apollosai.server.auth.auth_error import NoCredentialsError

    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    request = _make_mock_request()

    with pytest.raises(NoCredentialsError):
        await EntraIDUserAuth.get_instance(request)


@pytest.mark.asyncio
async def test_allow_unauthenticated_false_string_is_not_truthy(
    monkeypatch, _set_jwt_secret
):
    """SECURITY: APOLLOSAI_ALLOW_UNAUTHENTICATED=false must NOT enable bypass."""
    from apollosai.server.auth.auth_error import NoCredentialsError

    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', 'false')
    request = _make_mock_request()

    with pytest.raises(NoCredentialsError):
        await EntraIDUserAuth.get_instance(request)

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _set_entra_env(monkeypatch):
    monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant')
    monkeypatch.setenv('ENTRA_CLIENT_ID', 'test-client')
    monkeypatch.setenv('ENTRA_CLIENT_SECRET', 'test-secret')
    monkeypatch.setenv('ENTRA_REDIRECT_URI', 'http://localhost:3000/api/auth/callback')


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_get_msal_app_returns_confidential_client(mock_cca):
    from apollosai.server.auth.msal_client import get_msal_app

    mock_cca.return_value = MagicMock()
    app = get_msal_app()
    assert app is not None
    mock_cca.assert_called_once_with(
        client_id='test-client',
        client_credential='test-secret',
        authority='https://login.microsoftonline.com/test-tenant',
        token_cache=None,
    )


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_get_msal_app_passes_cache(mock_cca):
    from apollosai.server.auth.msal_client import get_msal_app

    mock_cache = MagicMock()
    mock_cca.return_value = MagicMock()
    get_msal_app(cache=mock_cache)
    mock_cca.assert_called_once_with(
        client_id='test-client',
        client_credential='test-secret',
        authority='https://login.microsoftonline.com/test-tenant',
        token_cache=mock_cache,
    )


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_get_auth_url_returns_url(mock_cca):
    from apollosai.server.auth.msal_client import get_auth_url

    mock_app = MagicMock()
    mock_app.initiate_auth_code_flow.return_value = {
        'auth_uri': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/authorize?...',
        'state': 'test-state',
    }
    mock_cca.return_value = mock_app

    result = get_auth_url(state='test-state')
    assert 'auth_uri' in result
    assert 'state' in result
    mock_app.initiate_auth_code_flow.assert_called_once_with(
        scopes=['User.Read'],
        redirect_uri='http://localhost:3000/api/auth/callback',
        state='test-state',
    )


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_get_auth_url_includes_openid_scope(mock_cca):
    from apollosai.server.auth.msal_client import get_auth_url

    mock_app = MagicMock()
    mock_app.initiate_auth_code_flow.return_value = {
        'auth_uri': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/authorize',
        'state': 'test-state',
    }
    mock_cca.return_value = mock_app

    result = get_auth_url(state='test-state')
    assert result['auth_uri'] is not None


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_acquire_token_by_auth_code_flow(mock_cca):
    from apollosai.server.auth.msal_client import acquire_token_by_auth_code_flow

    mock_app = MagicMock()
    mock_app.acquire_token_by_auth_code_flow.return_value = {
        'access_token': 'fake-access-token',
        'id_token_claims': {'sub': 'user-123'},
    }
    mock_cca.return_value = mock_app

    auth_code_flow = {'state': 'test-state', 'code_verifier': 'verifier'}
    auth_response = {'code': 'auth-code', 'state': 'test-state'}

    result = acquire_token_by_auth_code_flow(auth_code_flow, auth_response)
    assert result['access_token'] == 'fake-access-token'
    assert result['id_token_claims']['sub'] == 'user-123'
    mock_app.acquire_token_by_auth_code_flow.assert_called_once_with(
        auth_code_flow=auth_code_flow,
        auth_response=auth_response,
    )


@patch('apollosai.server.auth.msal_client.msal.ConfidentialClientApplication')
def test_acquire_token_by_auth_code_flow_error(mock_cca):
    from apollosai.server.auth.msal_client import acquire_token_by_auth_code_flow

    mock_app = MagicMock()
    mock_app.acquire_token_by_auth_code_flow.return_value = {
        'error': 'invalid_grant',
        'error_description': 'Code expired',
    }
    mock_cca.return_value = mock_app

    result = acquire_token_by_auth_code_flow({}, {})
    assert 'error' in result
    assert result['error'] == 'invalid_grant'


def test_constants_are_not_module_level():
    """Module-level constants break monkeypatch — only getter functions should exist."""
    import apollosai.server.auth.constants as c

    assert not hasattr(c, 'ENTRA_TENANT_ID'), 'Should be getter function, not constant'
    assert not hasattr(c, 'ENTRA_CLIENT_ID'), 'Should be getter function, not constant'
    assert not hasattr(c, 'ENTRA_REDIRECT_URI'), (
        'Should be getter function, not constant'
    )

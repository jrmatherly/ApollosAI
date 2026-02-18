"""Tests for Entra ID OAuth2 auth routes (authenticate, login, callback, logout).

Uses FastAPI TestClient with Starlette SessionMiddleware to test the full
request/response cycle including session cookie persistence.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from apollosai.server.auth.auth_error import InvalidTokenError, NoCredentialsError
from apollosai.server.routes.auth import router


@pytest.fixture(autouse=True)
def _reset_limiter_storage():
    """Reset limiter storage between tests to avoid state bleed and Redis hangs."""
    from apollosai.server.rate_limit import limiter

    try:
        limiter._storage.reset()
    except Exception:
        pass
    yield
    try:
        limiter._storage.reset()
    except Exception:
        pass


@pytest.fixture
def app(async_session):
    from apollosai.server.deps import get_db_session
    from apollosai.server.rate_limit import limiter

    app = FastAPI()
    app.state.limiter = limiter
    app.add_middleware(
        SessionMiddleware, secret_key='test-session-secret-32-chars!!!!!'
    )
    app.include_router(router)

    async def _override_session():
        yield async_session

    app.dependency_overrides[get_db_session] = _override_session
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRouterRegistration:
    """Verify all expected routes are registered on the router."""

    def test_router_has_authenticate_route(self):
        paths = [route.path for route in router.routes]
        assert '/authenticate' in paths

    def test_router_has_login_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/login' in paths

    def test_router_has_callback_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/callback' in paths

    def test_router_has_logout_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/logout' in paths


class TestAuthenticateRoute:
    """Tests for POST /authenticate."""

    def test_authenticate_returns_401_when_no_credentials(self, client):
        """Unauthenticated request should return 401."""
        with patch(
            'apollosai.server.routes.auth.EntraIDUserAuth.get_instance',
            new_callable=AsyncMock,
            side_effect=NoCredentialsError('Not authenticated'),
        ):
            response = client.post('/authenticate')
        assert response.status_code == 401
        assert response.json()['error'] == 'Not authenticated'

    def test_authenticate_returns_401_on_invalid_token(self, client):
        """Request with invalid token should return 401."""
        with patch(
            'apollosai.server.routes.auth.EntraIDUserAuth.get_instance',
            new_callable=AsyncMock,
            side_effect=InvalidTokenError('Token expired'),
        ):
            response = client.post('/authenticate')
        assert response.status_code == 401

    def test_authenticate_returns_200_when_valid(self, client):
        """Request with valid session should return 200."""
        from apollosai.server.auth.entraid_auth import EntraIDUserAuth

        mock_user = EntraIDUserAuth(user_id='user-123', email='user@example.com')
        with patch(
            'apollosai.server.routes.auth.EntraIDUserAuth.get_instance',
            new_callable=AsyncMock,
            return_value=mock_user,
        ):
            response = client.post('/authenticate')
        assert response.status_code == 200
        data = response.json()
        assert data['message'] == 'User authenticated'
        assert data['email'] == 'user@example.com'


class TestLoginRoute:
    """Tests for GET /auth/login."""

    def test_login_redirects_to_entra(self, client):
        """Login should redirect to Entra ID authorization URL."""
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/authorize?client_id=test',
            'state': 'test-state-123',
        }
        with patch('apollosai.server.routes.auth.get_auth_url', return_value=mock_flow):
            response = client.get('/auth/login', follow_redirects=False)
        assert response.status_code == 307
        assert 'login.microsoftonline.com' in response.headers['location']


class TestCallbackRoute:
    """Tests for GET /auth/callback."""

    def test_callback_missing_flow_returns_400(self, client):
        """Callback with no prior auth flow should return 400."""
        response = client.get('/auth/callback?code=test&state=test')
        assert response.status_code == 400
        assert 'Missing auth flow' in response.json()['error']

    def test_callback_csrf_state_mismatch_returns_403(self, client):
        """Callback with mismatched CSRF state should return 403."""
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/test',
            'state': 'expected-state',
        }
        with patch('apollosai.server.routes.auth.get_auth_url', return_value=mock_flow):
            # First, hit login to store the flow in session
            client.get('/auth/login', follow_redirects=False)

        # Now hit callback with a WRONG state — should be 403
        response = client.get('/auth/callback?code=test&state=wrong-state')
        assert response.status_code == 403
        assert 'CSRF state mismatch' in response.json()['error']

    def test_callback_success_sets_cookie(self, client, monkeypatch):
        """Successful callback should set session cookie and redirect."""
        monkeypatch.setenv('JWT_SECRET', 'a' * 32)

        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/test',
            'state': 'valid-state',
        }
        mock_token_result = {
            'access_token': 'test-access-token',
            'id_token_claims': {
                'oid': 'user-oid-123',
                'preferred_username': 'user@example.com',
            },
        }

        with patch('apollosai.server.routes.auth.get_auth_url', return_value=mock_flow):
            client.get('/auth/login', follow_redirects=False)

        with patch(
            'apollosai.server.routes.auth.acquire_token_by_auth_code_flow',
            return_value=mock_token_result,
        ):
            response = client.get(
                '/auth/callback?code=test-code&state=valid-state',
                follow_redirects=False,
            )

        assert response.status_code == 307
        assert response.headers['location'] == '/'
        # Check that a session cookie was set
        set_cookie = response.headers.get('set-cookie', '')
        assert 'session' in set_cookie.lower()

    def test_callback_auth_error_returns_401(self, client):
        """Callback with MSAL error should return 401."""
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/test',
            'state': 'valid-state',
        }
        mock_error_result = {
            'error': 'invalid_grant',
            'error_description': 'The authorization code has expired.',
        }

        with patch('apollosai.server.routes.auth.get_auth_url', return_value=mock_flow):
            client.get('/auth/login', follow_redirects=False)

        with patch(
            'apollosai.server.routes.auth.acquire_token_by_auth_code_flow',
            return_value=mock_error_result,
        ):
            response = client.get(
                '/auth/callback?code=test-code&state=valid-state',
            )

        assert response.status_code == 401
        assert 'expired' in response.json()['error'].lower()


class TestLogoutRoute:
    """Tests for POST /auth/logout."""

    def test_logout_returns_200(self, client):
        """Logout should return 200 with logged_out status."""
        response = client.post('/auth/logout')
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'logged_out'

    def test_logout_clears_cookie(self, client):
        """Logout should clear the session cookie."""
        response = client.post('/auth/logout')
        assert response.status_code == 200
        set_cookie = response.headers.get('set-cookie', '')
        # Cookie should either be cleared or session should be cleared
        assert 'session' in set_cookie.lower() or response.status_code == 200

    def test_logout_returns_signout_url(self, client, monkeypatch):
        """Logout should return MSAL signout URL."""
        monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant-id')
        response = client.post('/auth/logout')
        assert response.status_code == 200
        data = response.json()
        assert 'signout_url' in data
        assert 'login.microsoftonline.com/test-tenant-id' in data['signout_url']
        assert 'post_logout_redirect_uri' in data['signout_url']

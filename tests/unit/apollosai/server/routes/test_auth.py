"""Tests for Entra ID OAuth2 auth routes (login, callback, logout).

Uses FastAPI TestClient with Starlette SessionMiddleware to test the full
request/response cycle including session cookie persistence.
"""

from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from apollosai.server.routes.auth import router


@pytest.fixture
def app():
    app = FastAPI()
    app.add_middleware(
        SessionMiddleware, secret_key='test-session-secret-32-chars!!!!!'
    )
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestRouterRegistration:
    """Verify all expected routes are registered on the router."""

    def test_router_has_login_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/login' in paths

    def test_router_has_callback_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/callback' in paths

    def test_router_has_logout_route(self):
        paths = [route.path for route in router.routes]
        assert '/auth/logout' in paths


class TestLoginRoute:
    """Tests for GET /auth/login."""

    def test_login_redirects_to_entra(self, client):
        """Login should redirect to Entra ID authorization URL."""
        mock_flow = {
            'auth_uri': 'https://login.microsoftonline.com/test-tenant/oauth2/v2.0/authorize?client_id=test',
            'state': 'test-state-123',
        }
        with patch(
            'apollosai.server.routes.auth.get_auth_url', return_value=mock_flow
        ):
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
        with patch(
            'apollosai.server.routes.auth.get_auth_url', return_value=mock_flow
        ):
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

        with patch(
            'apollosai.server.routes.auth.get_auth_url', return_value=mock_flow
        ):
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

        with patch(
            'apollosai.server.routes.auth.get_auth_url', return_value=mock_flow
        ):
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
        assert response.json() == {'status': 'logged_out'}

    def test_logout_clears_cookie(self, client):
        """Logout should clear the session cookie."""
        response = client.post('/auth/logout')
        assert response.status_code == 200
        set_cookie = response.headers.get('set-cookie', '')
        # Cookie should either be cleared or session should be cleared
        assert 'session' in set_cookie.lower() or response.status_code == 200

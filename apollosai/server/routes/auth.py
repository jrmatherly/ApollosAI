"""Entra ID OAuth2 auth routes: login, callback, logout.

Flow:
1. GET /auth/login -> redirect to Entra ID login page
2. GET /auth/callback -> exchange code for tokens, set JWT session cookie
3. POST /auth/logout -> clear session cookie
"""

import secrets

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from apollosai.server.auth.jwt_utils import create_session_token
from apollosai.server.auth.msal_client import (
    acquire_token_by_auth_code_flow,
    get_auth_url,
)

router = APIRouter()

# Cookie settings
COOKIE_NAME = 'session'
COOKIE_MAX_AGE = 86400  # 24 hours


@router.get('/auth/login')
async def login(request: Request):
    """Initiate Entra ID login flow."""
    state = secrets.token_urlsafe(32)
    flow = get_auth_url(state=state)

    # Store flow in session for callback validation.
    # WARNING: Starlette's cookie-based session has ~4KB limit. MSAL auth flows
    # can be 2-5KB. If the flow exceeds cookie size, the callback will fail.
    # TODO: Phase 2 — Switch to server-side session store (Redis or DB-backed)
    request.session['auth_flow'] = flow

    return RedirectResponse(url=flow['auth_uri'])


@router.get('/auth/callback')
async def callback(request: Request):
    """Handle Entra ID OAuth2 callback."""
    flow = request.session.get('auth_flow', {})
    if not flow:
        return JSONResponse(
            status_code=400,
            content={'error': 'Missing auth flow. Please login again.'},
        )

    # Defense-in-depth: explicit CSRF state verification before MSAL
    callback_state = request.query_params.get('state', '')
    expected_state = flow.get('state', '')
    if not callback_state or callback_state != expected_state:
        return JSONResponse(
            status_code=403,
            content={'error': 'CSRF state mismatch. Please login again.'},
        )

    result = acquire_token_by_auth_code_flow(
        auth_code_flow=flow,
        auth_response=dict(request.query_params),
    )

    if 'error' in result:
        return JSONResponse(
            status_code=401,
            content={'error': result.get('error_description', 'Authentication failed')},
        )

    # Extract user info from id_token claims
    claims = result.get('id_token_claims', {})
    user_id = claims.get('oid', '')
    email = claims.get('preferred_username', '')

    # Create session JWT
    token = create_session_token(
        user_id=user_id,
        email=email,
        entra_oid=user_id,
    )

    # Set HttpOnly cookie and redirect to app
    redirect_url = request.session.pop('redirect_after_login', '/')
    response = RedirectResponse(url=redirect_url)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=True,
        samesite='lax',
    )

    # Clear auth flow from session
    request.session.pop('auth_flow', None)

    return response


@router.post('/auth/logout')
async def logout(request: Request, response: Response):
    """Clear session cookie and server-side session state."""
    request.session.clear()
    response.delete_cookie(key=COOKIE_NAME)
    return {'status': 'logged_out'}

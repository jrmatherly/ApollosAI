"""Entra ID OAuth2 auth routes: login, callback, logout, authenticate.

Flow:
1. POST /authenticate -> check session cookie/bearer token, return 200 or 401
2. GET /auth/login -> redirect to Entra ID login page
3. GET /auth/callback -> exchange code for tokens, set JWT session cookie
4. POST /auth/logout -> clear session cookie, revoke JWT, return MSAL signout URL
"""

import datetime
import secrets
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from apollosai.server.auth.auth_error import InvalidTokenError, NoCredentialsError
from apollosai.server.auth.constants import get_entra_tenant_id
from apollosai.server.auth.entraid_auth import EntraIDUserAuth
from apollosai.server.auth.jwt_utils import create_session_token, decode_session_token
from apollosai.server.auth.msal_client import (
    acquire_token_by_auth_code_flow,
    get_auth_url,
)
from apollosai.server.deps import get_db_session
from apollosai.server.rate_limit import limiter
from apollosai.storage.services.token_revocation_service import revoke_token

router = APIRouter()

# Cookie settings
COOKIE_NAME = 'session'
COOKIE_MAX_AGE = 86400  # 24 hours


@router.post('/authenticate')
@limiter.limit('30/minute')
async def authenticate(request: Request):
    """Check whether the current request has a valid session.

    The frontend calls this endpoint on page load to determine auth status.
    Returns 200 if the user has a valid session cookie or Bearer token,
    or 401 if not authenticated. This drives the login redirect flow:
    the frontend's useIsAuthed hook treats 401 as 'not authenticated'
    and redirects to /login.
    """
    try:
        user = await EntraIDUserAuth.get_instance(request)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'message': 'User authenticated',
                'email': user.email or '',
            },
        )
    except (NoCredentialsError, InvalidTokenError):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={'error': 'Not authenticated'},
        )


@router.get('/auth/login')
@limiter.limit('10/minute')
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
@limiter.limit('10/minute')
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
    # Review fix [L3]: Validate redirect URL to prevent open redirect attacks
    redirect_url = request.session.pop('redirect_after_login', '/')
    parsed = urlparse(redirect_url)
    if parsed.netloc and parsed.netloc != request.url.netloc:
        redirect_url = '/'  # Reject external redirects
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
@limiter.limit('10/minute')
async def logout(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_db_session),
):
    """Clear session cookie, revoke JWT, and clear server-side session state."""
    # Revoke the current JWT if present
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            payload = decode_session_token(token)
            jti = payload.get('jti')
            if jti:
                expires_at = datetime.datetime.fromtimestamp(
                    payload['exp'],
                    tz=datetime.timezone.utc,
                )
                await revoke_token(session, jti, expires_at)
        except Exception:
            pass  # Token may be expired/invalid — still clear the cookie

    request.session.clear()
    response.delete_cookie(key=COOKIE_NAME)

    # Build Microsoft signout URL for frontend to redirect to
    # Review fix [M6]: Return JSON with signout_url (not a redirect) so
    # the frontend can handle the flow: call logout API, then redirect.
    tenant = get_entra_tenant_id()
    # Use the app's base URL as post-logout redirect
    base_url = str(request.base_url).rstrip('/')
    signout_url = (
        f'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/logout'
        f'?post_logout_redirect_uri={quote(base_url, safe="")}'
    )
    return {'status': 'logged_out', 'signout_url': signout_url}

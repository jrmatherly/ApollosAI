"""ApollosAI enterprise entrypoint.

Run with:
    PYTHONPATH=".:$PYTHONPATH" uvicorn apollosai.app_server:app --host 0.0.0.0 --port 3000
"""

import os

from dotenv import load_dotenv

load_dotenv()

from apollosai.bootstrap import ensure_config_cls  # noqa: E402

ensure_config_cls()

# Now safe to import OpenHands — config class will be resolved via get_impl()
import socketio  # noqa: E402
from fastapi import Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from apollosai.server.auth.auth_error import (  # noqa: E402
    InvalidTokenError,
    NoCredentialsError,
)
from apollosai.server.routes.auth import router as auth_router  # noqa: E402
from openhands.server.app import app as base_app  # noqa: E402
from openhands.server.listen_socket import sio  # noqa: E402
from openhands.server.middleware import CacheControlMiddleware  # noqa: E402
from openhands.server.static import SPAStaticFiles  # noqa: E402

directory = os.getenv('FRONTEND_DIRECTORY', './frontend/build')


# Health check
@base_app.get('/apollosai')
def is_apollosai():
    return {'apollosai': True}


# Exception handlers — return proper 401 instead of 500 for auth errors
@base_app.exception_handler(NoCredentialsError)
async def no_credentials_handler(request: Request, exc: NoCredentialsError):
    return JSONResponse(status_code=401, content={'error': 'Not authenticated'})


@base_app.exception_handler(InvalidTokenError)
async def invalid_token_handler(request: Request, exc: InvalidTokenError):
    return JSONResponse(status_code=401, content={'error': 'Invalid or expired token'})


# Auth routes — login/callback/logout at /api/auth/*
base_app.include_router(auth_router, prefix='/api')

# Session middleware — required for auth flow state (request.session)
# Use a SEPARATE secret for session middleware (not JWT_SECRET)
import secrets as _secrets  # noqa: E402
import warnings as _warnings  # noqa: E402

from starlette.middleware.sessions import SessionMiddleware  # noqa: E402

_session_secret = os.environ.get('SESSION_SECRET', '')
if not _session_secret:
    _warnings.warn(
        'SESSION_SECRET not set — using random session key. '
        'Sessions will not survive restarts and multi-instance deployments will break. '
        'Set SESSION_SECRET to a random 32+ character string in production.',
        stacklevel=1,
    )
    _session_secret = _secrets.token_urlsafe(32)

base_app.add_middleware(SessionMiddleware, secret_key=_session_secret)

# CORS — required for frontend on different port/domain to reach API
allowed_origins = os.environ.get(
    'APOLLOSAI_CORS_ORIGINS', 'http://localhost:3001'
).split(',')
base_app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Cache control
base_app.add_middleware(CacheControlMiddleware)

# Static files
if os.path.isdir(directory):
    base_app.mount('/', SPAStaticFiles(directory=directory, html=True), name='dist')

# ASGI app
app = socketio.ASGIApp(sio, other_asgi_app=base_app)

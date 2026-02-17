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

from openhands.server.app import app as base_app  # noqa: E402
from openhands.server.listen_socket import sio  # noqa: E402
from openhands.server.middleware import CacheControlMiddleware  # noqa: E402
from openhands.server.static import SPAStaticFiles  # noqa: E402

from apollosai.server.auth.auth_error import NoCredentialsError  # noqa: E402

directory = os.getenv('FRONTEND_DIRECTORY', './frontend/build')


# Health check
@base_app.get('/apollosai')
def is_apollosai():
    return {'apollosai': True}


# Exception handlers — return proper 401 instead of 500 for auth errors
@base_app.exception_handler(NoCredentialsError)
async def no_credentials_handler(request: Request, exc: NoCredentialsError):
    return JSONResponse(status_code=401, content={'error': 'Not authenticated'})


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

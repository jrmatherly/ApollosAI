"""Auth constants — all config accessed via getter functions.

Values are NOT stored as module-level constants to prevent accidental leakage
in error reports, logging middleware, or repr() calls on the module namespace,
and to ensure monkeypatch compatibility in tests.
"""

import os


def get_entra_tenant_id() -> str:
    """Get Entra ID tenant ID from environment at call time."""
    return os.environ.get('ENTRA_TENANT_ID', '')


def get_entra_client_id() -> str:
    """Get Entra ID client ID from environment at call time."""
    return os.environ.get('ENTRA_CLIENT_ID', '')


def get_entra_redirect_uri() -> str:
    """Get Entra ID redirect URI from environment at call time.

    Defaults to http://localhost:3000/api/auth/callback if not set.
    The /api prefix is required because the auth router is mounted
    at /api in apollosai/app_server.py.
    """
    return os.environ.get(
        'ENTRA_REDIRECT_URI', 'http://localhost:3000/api/auth/callback'
    )


def get_entra_client_secret() -> str:
    """Get Entra ID client secret from environment at call time."""
    return os.environ.get('ENTRA_CLIENT_SECRET', '')


def get_jwt_secret() -> str:
    """Get JWT signing secret from environment at call time."""
    return os.environ.get('JWT_SECRET', '')

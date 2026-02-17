"""Auth constants — secrets accessed via getter functions to avoid module-level exposure.

Secrets are NOT stored as module-level constants to prevent accidental leakage
in error reports, logging middleware, or repr() calls on the module namespace.
"""

import os

# Non-secret configuration (safe as module constants)
ENTRA_TENANT_ID = os.environ.get('ENTRA_TENANT_ID', '')
ENTRA_CLIENT_ID = os.environ.get('ENTRA_CLIENT_ID', '')
ENTRA_REDIRECT_URI = os.environ.get('ENTRA_REDIRECT_URI', '')


def get_entra_client_secret() -> str:
    """Get Entra ID client secret from environment at call time."""
    return os.environ.get('ENTRA_CLIENT_SECRET', '')


def get_jwt_secret() -> str:
    """Get JWT signing secret from environment at call time."""
    return os.environ.get('JWT_SECRET', '')

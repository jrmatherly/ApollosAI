"""Rate limiting configuration for ApollosAI.

Uses slowapi with in-memory storage by default.
Set REDIS_URL environment variable for Redis-backed storage
in multi-instance deployments.

The limiter is created eagerly (required by slowapi decorator wiring)
but storage URI resolution is deferred to first request via
``_resolve_storage_uri`` so that module-level imports never block
on a Redis TCP handshake.
"""

import os
import warnings

from slowapi import Limiter
from slowapi.util import get_remote_address


def _resolve_storage_uri() -> str | None:
    """Return REDIS_URL if set, else None (in-memory fallback).

    Called lazily — safe to import this module without a reachable Redis.
    """
    uri = os.environ.get('REDIS_URL')
    if not uri:
        warnings.warn(
            'Rate limiting uses in-memory storage — ineffective with multiple workers. '
            'Set REDIS_URL for production deployments.',
            stacklevel=2,
        )
    return uri


# Create with in-memory storage at import time (no network I/O).
# The app startup hook in app_server.py re-initialises with Redis
# when REDIS_URL is available.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=None,
)

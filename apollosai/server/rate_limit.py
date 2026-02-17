"""Rate limiting configuration for ApollosAI.

Uses slowapi with in-memory storage by default.
Set REDIS_URL environment variable for Redis-backed storage
in multi-instance deployments.
"""

import os
import warnings

from slowapi import Limiter
from slowapi.util import get_remote_address

storage_uri = os.environ.get('REDIS_URL')
if not storage_uri:
    warnings.warn(
        'Rate limiting uses in-memory storage — ineffective with multiple workers. '
        'Set REDIS_URL for production deployments.',
        stacklevel=2,
    )

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=storage_uri,
)

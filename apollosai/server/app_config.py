"""V1 AppServerConfig factory for ApollosAI.

Creates an AppServerConfig with ApollosAI-specific injectors.
Called during V1 server initialization when enable_v1=True.
"""

from openhands.app_server.config import AppServerConfig
from openhands.server.types import AppMode

from apollosai.server.auth.user_context import EntraIDUserContextInjector
from apollosai.server.lifespan import ApollosAILifespanService


def create_apollosai_app_config() -> AppServerConfig:
    """Create AppServerConfig with ApollosAI injectors.

    Phase 1.5 scope: Only `user`, `lifespan`, and `app_mode` are customized.
    All other injectors (event, sandbox, conversation, db_session, etc.)
    default to None. This is intentional — Phase 1.5 only wires auth and
    lifespan. V1 routes that depend on other injectors are not yet active.

    Phase 2 will add:
    - Custom DbSessionInjector using apollosai/storage/database.py (PostgreSQL)
      instead of the default SQLite-based DbSessionInjector
    - Conversation, event, and sandbox injectors as needed
    """
    return AppServerConfig(
        user=EntraIDUserContextInjector(),
        lifespan=ApollosAILifespanService(),
        app_mode=AppMode.SAAS,
    )

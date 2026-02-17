"""ApollosAI lifespan service — manages startup/shutdown for the enterprise server.

Overrides OssAppLifespanService to:
1. Skip OpenHands' Alembic migrations (we have our own chain)
2. Run ApollosAI Alembic migrations against PostgreSQL (Phase 2)
3. Initialize async engine on startup (Phase 2)
"""

from openhands.app_server.app_lifespan.oss_app_lifespan_service import (
    OssAppLifespanService,
)


class ApollosAILifespanService(OssAppLifespanService):
    """Enterprise lifespan service.

    Inherits from OssAppLifespanService (not the abstract AppLifespanService)
    to reuse non-migration startup logic (event store init, etc.).

    We only override `run_alembic_on_startup` to prevent OpenHands' SQLite
    Alembic migrations from running — ApollosAI has its own PostgreSQL
    migration chain at apollosai/migrations/.

    NOTE (Phase 2): Override __aenter__ to run ApollosAI's own Alembic
    migrations and initialize the async engine pool. Override __aexit__
    to dispose the async engine. For Phase 1.5, migrations are run
    manually via `alembic -c apollosai/alembic.ini upgrade head`.
    """

    run_alembic_on_startup: bool = False

from apollosai.server.lifespan import ApollosAILifespanService
from openhands.app_server.app_lifespan.app_lifespan_service import AppLifespanService


def test_is_subclass():
    assert issubclass(ApollosAILifespanService, AppLifespanService)


def test_does_not_run_openhands_migrations():
    """ApollosAI has its own Alembic chain — must not run OpenHands migrations."""
    service = ApollosAILifespanService()
    assert service.run_alembic_on_startup is False


def test_has_async_context_manager_protocol():
    """Must support async with for lifespan management."""
    service = ApollosAILifespanService()
    assert hasattr(service, '__aenter__')
    assert hasattr(service, '__aexit__')

"""Registry for discovering and accessing integration managers."""

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import IntegrationType

_registry: dict[IntegrationType, type[ApollosAIIntegrationManager]] = {}


def register_integration(
    source_type: IntegrationType, manager_cls: type[ApollosAIIntegrationManager]
) -> None:
    """Register an integration manager class for a source type."""
    _registry[source_type] = manager_cls


def get_integration(
    source_type: IntegrationType,
) -> type[ApollosAIIntegrationManager] | None:
    """Look up the registered manager class for a source type."""
    return _registry.get(source_type)


def list_integrations() -> list[IntegrationType]:
    """Return all registered source types."""
    return list(_registry.keys())


def clear_registry() -> None:
    """Clear all registrations. Intended for testing only."""
    _registry.clear()

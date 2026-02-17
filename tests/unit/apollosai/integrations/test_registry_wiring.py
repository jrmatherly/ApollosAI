"""Tests that all integration managers are registered at startup."""

from apollosai.integrations.models import IntegrationType
from apollosai.integrations.registry import clear_registry, get_integration


def test_all_managers_registered():
    """Importing register_all populates the registry with all 5 managers."""
    clear_registry()
    from apollosai.integrations.register_all import register_all_integrations

    register_all_integrations()

    for source in [
        IntegrationType.GITHUB,
        IntegrationType.JIRA,
        IntegrationType.SLACK,
        IntegrationType.BITBUCKET,
        IntegrationType.MICROSOFT,
    ]:
        cls = get_integration(source)
        assert cls is not None, f'{source.value} not registered'
        assert hasattr(cls, 'source_type')

    clear_registry()

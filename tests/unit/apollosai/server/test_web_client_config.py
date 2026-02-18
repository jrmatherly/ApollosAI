"""Tests for ApollosAI WebClientConfigInjector."""

import pytest

from apollosai.server.web_client_config import (
    ApollosAIWebClientConfigInjector,
    _get_providers_configured,
)
from openhands.integrations.service_types import ProviderType


class TestGetProvidersConfigured:
    """Tests for _get_providers_configured helper."""

    def test_returns_enterprise_sso_when_entra_configured(self, monkeypatch):
        monkeypatch.setenv('ENTRA_CLIENT_ID', 'test-client-id')
        monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant-id')
        providers = _get_providers_configured()
        assert ProviderType.ENTERPRISE_SSO in providers

    def test_returns_empty_when_no_entra_vars(self, monkeypatch):
        monkeypatch.delenv('ENTRA_CLIENT_ID', raising=False)
        monkeypatch.delenv('ENTRA_TENANT_ID', raising=False)
        providers = _get_providers_configured()
        assert providers == []

    def test_returns_empty_when_only_client_id(self, monkeypatch):
        monkeypatch.setenv('ENTRA_CLIENT_ID', 'test-client-id')
        monkeypatch.delenv('ENTRA_TENANT_ID', raising=False)
        providers = _get_providers_configured()
        assert providers == []

    def test_returns_empty_when_only_tenant_id(self, monkeypatch):
        monkeypatch.delenv('ENTRA_CLIENT_ID', raising=False)
        monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant-id')
        providers = _get_providers_configured()
        assert providers == []

    def test_returns_empty_when_blank_values(self, monkeypatch):
        monkeypatch.setenv('ENTRA_CLIENT_ID', '  ')
        monkeypatch.setenv('ENTRA_TENANT_ID', '  ')
        providers = _get_providers_configured()
        assert providers == []


class TestApollosAIWebClientConfigInjector:
    """Tests for ApollosAIWebClientConfigInjector."""

    def test_posthog_key_is_none(self):
        injector = ApollosAIWebClientConfigInjector()
        assert injector.posthog_client_key is None

    def test_inherits_default_injector(self):
        from openhands.app_server.web_client.default_web_client_config_injector import (
            DefaultWebClientConfigInjector,
        )

        assert issubclass(
            ApollosAIWebClientConfigInjector, DefaultWebClientConfigInjector
        )

    @pytest.mark.asyncio
    async def test_get_web_client_config_includes_providers(self, monkeypatch):
        monkeypatch.setenv('ENTRA_CLIENT_ID', 'test-client-id')
        monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant-id')
        injector = ApollosAIWebClientConfigInjector(
            providers_configured=_get_providers_configured()
        )

        # Mock get_global_config to return a minimal config
        from unittest.mock import MagicMock

        mock_config = MagicMock()
        mock_config.app_mode = 'saas'
        monkeypatch.setattr(
            'openhands.app_server.web_client.default_web_client_config_injector.get_global_config',
            lambda: mock_config,
        )

        config = await injector.get_web_client_config()
        assert ProviderType.ENTERPRISE_SSO in config.providers_configured

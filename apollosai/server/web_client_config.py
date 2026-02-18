"""ApollosAI WebClientConfigInjector — includes enterprise_sso provider."""

import os

from pydantic import Field

from openhands.app_server.web_client.default_web_client_config_injector import (
    DefaultWebClientConfigInjector,
)
from openhands.integrations.service_types import ProviderType


def _get_providers_configured() -> list[ProviderType]:
    """Build the list of configured auth providers.

    Checks environment variables to determine which identity providers
    are available. The frontend login page uses this to show the correct
    auth buttons (e.g. 'Sign in with Microsoft').
    """
    providers: list[ProviderType] = []

    # Entra ID (Microsoft) SSO
    entra_client_id = os.environ.get('ENTRA_CLIENT_ID', '').strip()
    entra_tenant_id = os.environ.get('ENTRA_TENANT_ID', '').strip()
    if entra_client_id and entra_tenant_id:
        providers.append(ProviderType.ENTERPRISE_SSO)

    return providers


class ApollosAIWebClientConfigInjector(DefaultWebClientConfigInjector):
    """WebClientConfigInjector with ApollosAI auth providers.

    Extends the default injector to include enterprise_sso in
    providers_configured when Entra ID env vars are set.
    """

    posthog_client_key: str | None = None
    providers_configured: list[ProviderType] = Field(
        default_factory=_get_providers_configured
    )

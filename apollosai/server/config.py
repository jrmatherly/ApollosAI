import os

from openhands.server.config.server_config import ServerConfig
from openhands.server.types import AppMode


class ApollosAIServerConfig(ServerConfig):
    config_cls: str = os.environ.get('OPENHANDS_CONFIG_CLS', '')
    app_mode = AppMode.SAAS
    enable_billing = False
    hide_llm_settings = False
    enable_v1: bool = True

    settings_store_class: str = (
        'apollosai.storage.stores.settings_store.ApollosAISettingsStore'
    )
    secret_store_class: str = (
        'apollosai.storage.stores.secrets_store.ApollosAISecretsStore'
    )
    conversation_store_class: str = (
        'apollosai.storage.stores.conversation_store.ApollosAIConversationStore'
    )
    user_auth_class: str = 'apollosai.server.auth.entraid_auth.EntraIDUserAuth'
    monitoring_listener_class: str = 'openhands.server.monitoring.MonitoringListener'

    def verify_config(self):
        """Validate required environment variables for production.

        In production mode (APOLLOSAI_ALLOW_UNAUTHENTICATED not set),
        raises ValueError for missing required config. In dev mode,
        logs a warning instead.
        """
        from apollosai.server.auth.constants import (
            get_entra_client_id,
            get_entra_tenant_id,
            get_jwt_secret,
        )

        checks = {
            'ENTRA_TENANT_ID': get_entra_tenant_id(),
            'ENTRA_CLIENT_ID': get_entra_client_id(),
            'JWT_SECRET': get_jwt_secret(),
        }
        missing = [name for name, value in checks.items() if not value]
        if not missing:
            return
        # Parse APOLLOSAI_ALLOW_UNAUTHENTICATED explicitly (same as get_instance)
        allow_unauth = os.environ.get(
            'APOLLOSAI_ALLOW_UNAUTHENTICATED', ''
        ).lower() in ('1', 'true', 'yes')
        msg = (
            f'Missing required environment variables: {", ".join(missing)}. '
            'Set APOLLOSAI_ALLOW_UNAUTHENTICATED=1 for development.'
        )
        if allow_unauth:
            import logging

            logging.getLogger(__name__).warning(msg)
        else:
            raise ValueError(msg)

    def get_config(self):
        return {
            'APP_MODE': self.app_mode,
            'GITHUB_CLIENT_ID': self.github_client_id,
            'POSTHOG_CLIENT_KEY': '',
            'FEATURE_FLAGS': {
                'ENABLE_BILLING': False,
                'HIDE_LLM_SETTINGS': False,
            },
        }

import os

from openhands.server.config.server_config import ServerConfig
from openhands.server.types import AppMode


class ApollosAIServerConfig(ServerConfig):
    config_cls: str = os.environ.get('OPENHANDS_CONFIG_CLS', '')
    app_mode = AppMode.SAAS
    enable_billing = False
    hide_llm_settings = False
    # Disable V1 routes in Phase 1 — V1 UserContextInjector deferred to Phase 1.5.
    # Without V1 injectors configured, V1 routes would use the default bridge which
    # may not resolve to EntraIDUserAuth correctly.
    enable_v1: bool = False

    settings_store_class: str = (
        'apollosai.storage.stores.settings_store.ApollosAISettingsStore'
    )
    secret_store_class: str = (
        'apollosai.storage.stores.secrets_store.ApollosAISecretsStore'
    )
    conversation_store_class: str = (
        'apollosai.storage.stores.conversation_store.ApollosAIConversationStore'
    )
    user_auth_class: str = (
        'apollosai.server.auth.entraid_auth.EntraIDUserAuth'
    )
    monitoring_listener_class: str = (
        'openhands.server.monitoring.MonitoringListener'
    )

    def verify_config(self):
        pass

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

import os
from dataclasses import dataclass, field

from fastapi import Request
from pydantic import SecretStr

from apollosai.server.auth.auth_error import NoCredentialsError
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
from openhands.server.settings import Settings
from openhands.server.user_auth.user_auth import UserAuth
from openhands.storage.data_models.secrets import Secrets
from openhands.storage.secrets.secrets_store import SecretsStore
from openhands.storage.settings.settings_store import SettingsStore


@dataclass
class EntraIDUserAuth(UserAuth):
    """Entra ID auth implementing the V0 UserAuth ABC.

    Uses @dataclass (matching DefaultUserAuth pattern at default_user_auth.py:23).
    The _settings field is required by UserAuth.get_user_settings() which accesses
    self._settings directly (user_auth.py:67).
    """

    user_id: str | None = None
    email: str | None = None
    access_token: SecretStr | None = None
    refresh_token: SecretStr | None = None
    _settings: Settings | None = field(default=None, init=False, repr=False)

    async def get_user_id(self) -> str | None:
        return self.user_id

    async def get_user_email(self) -> str | None:
        return self.email

    async def get_access_token(self) -> SecretStr | None:
        return self.access_token

    async def get_provider_tokens(self) -> PROVIDER_TOKEN_TYPE | None:
        return None

    async def get_user_settings_store(self) -> SettingsStore:
        from apollosai.storage.stores.settings_store import ApollosAISettingsStore
        from openhands.core.config.utils import load_openhands_config

        config = load_openhands_config()
        return await ApollosAISettingsStore.get_instance(config, self.user_id)

    async def get_user_settings(self) -> Settings | None:
        """Get user settings, merging with config.toml values.

        Overrides UserAuth.get_user_settings() to match DefaultUserAuth's
        merge_with_config_settings() behavior (default_user_auth.py:66).
        """
        settings = self._settings
        if settings:
            return settings
        settings_store = await self.get_user_settings_store()
        settings = await settings_store.load()
        if settings:
            settings = settings.merge_with_config_settings()
        self._settings = settings
        return settings

    async def get_secrets_store(self) -> SecretsStore:
        from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
        from openhands.core.config.utils import load_openhands_config

        config = load_openhands_config()
        return await ApollosAISecretsStore.get_instance(config, self.user_id)

    async def get_secrets(self) -> Secrets | None:
        store = await self.get_secrets_store()
        return await store.load()

    async def get_mcp_api_key(self) -> str | None:
        return None

    @classmethod
    async def get_instance(cls, request: Request) -> 'EntraIDUserAuth':
        # Phase 1.5 will extract user from signed JWT cookie or Bearer API key.
        # Until then, require explicit opt-in for unauthenticated access to prevent
        # accidental deployment without auth.
        if not os.environ.get('APOLLOSAI_ALLOW_UNAUTHENTICATED'):
            raise NoCredentialsError(
                'Authentication not configured. '
                'Set APOLLOSAI_ALLOW_UNAUTHENTICATED=1 for development.'
            )
        return cls()

    @classmethod
    async def get_for_user(cls, user_id: str) -> 'EntraIDUserAuth':
        # TODO: Phase 1.5 — load cached tokens from DB
        return cls(user_id=user_id)

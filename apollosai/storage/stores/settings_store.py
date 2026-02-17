from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.settings import Settings
from openhands.storage.settings.settings_store import SettingsStore


class ApollosAISettingsStore(SettingsStore):
    """PostgreSQL-backed settings with Org -> Team -> User resolution."""

    def __init__(self, config: OpenHandsConfig, user_id: str | None):
        self.config = config
        self.user_id = user_id

    async def load(self) -> Settings | None:
        # TODO: Implement Org -> Team -> User resolution chain
        # Phase 1: Return default settings from config.
        # Note: Settings.from_config() returns None when no LLM API key is configured.
        # Fall back to empty Settings() to prevent downstream None propagation.
        result = Settings.from_config()
        return result if result is not None else Settings()

    async def store(self, settings: Settings) -> None:
        # TODO: Persist settings to appropriate tier (user/team/org)
        pass

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISettingsStore':
        return cls(config=config, user_id=user_id)

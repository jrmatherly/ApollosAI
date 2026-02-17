"""PostgreSQL-backed settings with Org -> Team -> User resolution.

Review fixes incorporated:
- [C1]: Uses get_session_maker() from lifespan module as V0 bridge
- [H8]: Uses request-scoped sessions via session_maker, not per-operation
- [C2-arch]: Field names verified against Settings.model_fields
"""

import uuid as uuid_mod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.settings import Settings
from openhands.storage.settings.settings_store import SettingsStore


class ApollosAISettingsStore(SettingsStore):
    """PostgreSQL-backed settings with Org -> Team -> User resolution."""

    def __init__(
        self,
        config: OpenHandsConfig | None,
        user_id: str | None,
        session_maker: async_sessionmaker | None = None,
    ):
        self.config = config
        self.user_id = user_id
        self.session_maker = session_maker

    async def load(self) -> Settings | None:
        """Load settings with Org -> Team -> User resolution chain.

        Falls back to config defaults if no DB session is available.
        """
        if self.session_maker is None or self.user_id is None:
            result = Settings.from_config()
            return result if result is not None else Settings()

        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        async with self.session_maker() as session:
            # Load user to get current org/team context
            user_uuid = uuid_mod.UUID(self.user_id)
            user = await session.get(User, user_uuid)
            if user is None:
                result = Settings.from_config()
                return result if result is not None else Settings()

            settings_dict: dict = {}

            # Layer 1: Org defaults
            if user.current_org_id:
                org = await session.get(Organization, user.current_org_id)
                if org:
                    if org.default_llm_model:
                        settings_dict['llm_model'] = org.default_llm_model
                    if org.default_llm_base_url:
                        settings_dict['llm_base_url'] = org.default_llm_base_url
                    if org.default_max_iterations:
                        settings_dict['max_iterations'] = org.default_max_iterations
                    if org.agent:
                        settings_dict['agent'] = org.agent

            # Layer 2: Team overrides
            if user.current_team_id:
                team = await session.get(Team, user.current_team_id)
                if team:
                    if team.llm_model:
                        settings_dict['llm_model'] = team.llm_model
                    if team.llm_base_url:
                        settings_dict['llm_base_url'] = team.llm_base_url
                    if team.max_iterations:
                        settings_dict['max_iterations'] = team.max_iterations

            # Layer 3: User overrides (from TeamMembership)
            if user.current_team_id:
                stmt = select(TeamMembership).where(
                    TeamMembership.team_id == user.current_team_id,
                    TeamMembership.user_id == user.id,
                )
                result = await session.execute(stmt)
                membership = result.scalar_one_or_none()
                if membership:
                    if membership.llm_model:
                        settings_dict['llm_model'] = membership.llm_model
                    if membership.max_iterations:
                        settings_dict['max_iterations'] = membership.max_iterations

            # Build Settings from resolved values
            base = Settings.from_config()
            if base is None:
                base = Settings()
            if settings_dict:
                base = base.model_copy(update=settings_dict)
            return base

    async def store(self, settings: Settings) -> None:
        """Persist settings — stores at user tier via TeamMembership overrides."""
        if self.session_maker is None or self.user_id is None:
            return

        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        async with self.session_maker() as session:
            user_uuid = uuid_mod.UUID(self.user_id)
            user = await session.get(User, user_uuid)
            if user is None or user.current_team_id is None:
                return

            stmt = select(TeamMembership).where(
                TeamMembership.team_id == user.current_team_id,
                TeamMembership.user_id == user.id,
            )
            result = await session.execute(stmt)
            membership = result.scalar_one_or_none()
            if membership:
                if settings.llm_model:
                    membership.llm_model = settings.llm_model
                if settings.max_iterations:
                    membership.max_iterations = settings.max_iterations
                await session.commit()

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISettingsStore':
        """Review fix [C1]: Bridge V0 ABC by getting session_maker from lifespan module."""
        from apollosai.server.lifespan import get_session_maker

        return cls(config=config, user_id=user_id, session_maker=get_session_maker())

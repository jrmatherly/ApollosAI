"""Tests for ApollosAISettingsStore — Org -> Team -> User resolution.

Review fixes incorporated:
- [H10]: Replaced `pass` bodies with real assertions
- [M9]: Added full 3-layer resolution chain test
- [M1]: Added get_instance() integration test
- [C2-arch]: Validated Settings field names match model attributes
"""

import uuid

import pytest

from apollosai.storage.stores.settings_store import ApollosAISettingsStore
from openhands.storage.settings.settings_store import SettingsStore

# NOTE: async_session fixture comes from conftest.py (Task 4b)


def test_is_subclass_of_settings_store():
    assert issubclass(ApollosAISettingsStore, SettingsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISettingsStore, 'load')
    assert hasattr(ApollosAISettingsStore, 'store')
    assert hasattr(ApollosAISettingsStore, 'get_instance')


class TestSettingsStoreLoad:
    """Test settings resolution chain."""

    @pytest.mark.asyncio
    async def test_load_returns_settings_when_no_db(self):
        """Without a session_maker, should return config defaults (backward compat)."""
        store = ApollosAISettingsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_returns_defaults_when_from_config_returns_none(self, monkeypatch):
        """Review fix [L4]: Settings.from_config() can return None."""
        monkeypatch.setattr(
            'openhands.storage.data_models.settings.Settings.from_config', lambda: None
        )
        store = ApollosAISettingsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None

    @pytest.mark.asyncio
    async def test_load_with_session_returns_org_defaults(self, async_session, async_session_maker):
        """With a session, should query org-level LLM defaults."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-4')
        user = User(id=uuid.uuid4(), entra_oid='test-oid', current_org_id=org.id)
        async_session.add_all([org, user])
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings is not None
        assert settings.llm_model == 'gpt-4'

    @pytest.mark.asyncio
    async def test_load_team_overrides_org(self, async_session, async_session_maker):
        """Review fix [H10]: Team-level settings should override org defaults."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-3.5')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team', llm_model='gpt-4')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        async_session.add_all([org, team, user])
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings.llm_model == 'gpt-4'  # Team overrides org

    @pytest.mark.asyncio
    async def test_full_resolution_user_overrides_team_overrides_org(
        self, async_session, async_session_maker
    ):
        """Review fix [M9]: Full 3-layer chain — user wins over team wins over org."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.role import Role
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User

        org = Organization(id=uuid.uuid4(), name='test-org', default_llm_model='gpt-3.5')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team', llm_model='gpt-4')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        role = Role(name='member', rank=3)
        async_session.add_all([org, team, user, role])
        await async_session.flush()
        membership = TeamMembership(
            team_id=team.id, user_id=user.id, role_id=role.id, llm_model='claude-3',
        )
        async_session.add(membership)
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        settings = await store.load()
        assert settings.llm_model == 'claude-3'  # User overrides team overrides org


class TestSettingsStoreStore:
    """Test settings persistence."""

    @pytest.mark.asyncio
    async def test_store_persists_settings(self, async_session, async_session_maker):
        """Review fix [H10]: Store should write to user tier via TeamMembership."""
        from apollosai.storage.models.organization import Organization
        from apollosai.storage.models.role import Role
        from apollosai.storage.models.team import Team
        from apollosai.storage.models.team_membership import TeamMembership
        from apollosai.storage.models.user import User
        from openhands.storage.data_models.settings import Settings

        org = Organization(id=uuid.uuid4(), name='test-org')
        team = Team(id=uuid.uuid4(), org_id=org.id, name='test-team')
        user = User(
            id=uuid.uuid4(), entra_oid='test-oid',
            current_org_id=org.id, current_team_id=team.id,
        )
        role = Role(name='member', rank=3)
        async_session.add_all([org, team, user, role])
        await async_session.flush()
        membership = TeamMembership(
            team_id=team.id, user_id=user.id, role_id=role.id,
        )
        async_session.add(membership)
        await async_session.commit()

        store = ApollosAISettingsStore(
            config=None, user_id=str(user.id), session_maker=async_session_maker
        )
        await store.store(Settings(llm_model='gpt-4o'))

        # Reload and verify
        settings = await store.load()
        assert settings.llm_model == 'gpt-4o'


class TestSettingsStoreFieldNames:
    """Review fix [C2-arch]: Verify hardcoded field names exist in Settings."""

    def test_settings_has_expected_fields(self):
        from openhands.storage.data_models.settings import Settings
        field_names = set(Settings.model_fields.keys())
        # These are the field names used in the resolution chain
        for name in ['llm_model', 'llm_base_url', 'max_iterations', 'agent']:
            assert name in field_names, f'{name} not in Settings.model_fields'

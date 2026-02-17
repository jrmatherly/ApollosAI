"""Tests for ApollosAISecretsStore — encrypted secret storage.

Review fix [C9]: Full test implementations for security-critical encrypted storage.
Review fix [M14]: AAD mismatch tests for tenant isolation.

Note: Plan used Secrets(llm_api_key=...) but Secrets model only has
provider_tokens and custom_secrets. Tests adapted to actual interface.
"""

import uuid

import cryptography.exceptions
import pytest
from pydantic import SecretStr

from apollosai.storage.stores.secrets_store import ApollosAISecretsStore
from openhands.integrations.provider import CustomSecret
from openhands.storage.data_models.secrets import Secrets
from openhands.storage.secrets.secrets_store import SecretsStore

# NOTE: async_session fixture from conftest.py (Task 4b)


def test_is_subclass_of_secrets_store():
    assert issubclass(ApollosAISecretsStore, SecretsStore)


def test_has_required_methods():
    assert hasattr(ApollosAISecretsStore, 'load')
    assert hasattr(ApollosAISecretsStore, 'store')
    assert hasattr(ApollosAISecretsStore, 'get_instance')


class TestSecretsStoreLoad:
    @pytest.mark.asyncio
    async def test_load_returns_empty_when_no_session(self):
        """Backward compat: no DB session should return empty Secrets()."""
        store = ApollosAISecretsStore(config=None, user_id=None)
        result = await store.load()
        assert result is not None
        assert isinstance(result, Secrets)

    @pytest.mark.asyncio
    async def test_load_returns_empty_when_no_records(
        self, async_session, async_session_maker
    ):
        """No DB records should return empty Secrets(), not None or error."""
        from apollosai.storage.models.user import User

        user_id = uuid.uuid4()
        user = User(
            id=user_id, entra_oid='no-records-test', current_org_id=uuid.uuid4()
        )
        async_session.add(user)
        await async_session.commit()

        store = ApollosAISecretsStore(
            config=None, user_id=str(user_id), session_maker=async_session_maker
        )
        result = await store.load()
        assert result is not None


class TestSecretsStoreRoundtrip:
    @pytest.mark.asyncio
    async def test_store_and_load_roundtrip(
        self, async_session, async_session_maker, monkeypatch
    ):
        """Stored secrets should be retrievable via load()."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import reset_key_cache

        reset_key_cache()

        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        from apollosai.storage.models.user import User

        user = User(id=user_id, entra_oid='roundtrip-test', current_org_id=org_id)
        async_session.add(user)
        await async_session.commit()

        store = ApollosAISecretsStore(
            config=None, user_id=str(user_id), session_maker=async_session_maker
        )
        secrets = Secrets(
            custom_secrets={
                'LLM_API_KEY': CustomSecret(
                    secret=SecretStr('sk-test-key-12345'), description='Test key'
                ),
            }
        )
        await store.store(secrets)

        loaded = await store.load()
        assert (
            loaded.custom_secrets['LLM_API_KEY'].secret.get_secret_value()
            == 'sk-test-key-12345'
        )

    @pytest.mark.asyncio
    async def test_store_upserts_existing_key(
        self, async_session, async_session_maker, monkeypatch
    ):
        """Storing a secret for an existing key should update, not duplicate."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import reset_key_cache

        reset_key_cache()

        user_id = uuid.uuid4()
        org_id = uuid.uuid4()
        from apollosai.storage.models.user import User

        user = User(id=user_id, entra_oid='upsert-test', current_org_id=org_id)
        async_session.add(user)
        await async_session.commit()

        store = ApollosAISecretsStore(
            config=None, user_id=str(user_id), session_maker=async_session_maker
        )
        await store.store(
            Secrets(
                custom_secrets={
                    'KEY': CustomSecret(secret=SecretStr('v1'), description=''),
                }
            )
        )
        await store.store(
            Secrets(
                custom_secrets={
                    'KEY': CustomSecret(secret=SecretStr('v2'), description=''),
                }
            )
        )

        loaded = await store.load()
        assert loaded.custom_secrets['KEY'].secret.get_secret_value() == 'v2'


class TestSecretsStoreAAD:
    """Review fix [M14]: AAD-based tenant isolation."""

    def test_decrypt_with_wrong_aad_raises(self, monkeypatch):
        """Secrets encrypted with user_a:org_a must not decrypt with user_b:org_b."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import (
            decrypt_value,
            encrypt_value,
            reset_key_cache,
        )

        reset_key_cache()

        encrypted = encrypt_value('secret', aad='user1:org1')
        with pytest.raises(cryptography.exceptions.InvalidTag):
            decrypt_value(encrypted, aad='user2:org2')

    def test_encrypt_decrypt_with_aad_roundtrip(self, monkeypatch):
        """Matching AAD should decrypt successfully."""
        monkeypatch.setenv('APOLLOSAI_ENCRYPTION_KEY', 'a' * 32)
        from apollosai.storage.encrypt_utils import (
            decrypt_value,
            encrypt_value,
            reset_key_cache,
        )

        reset_key_cache()

        aad = 'user-uuid:org-uuid'
        encrypted = encrypt_value('my-api-key', aad=aad)
        assert decrypt_value(encrypted, aad=aad) == 'my-api-key'

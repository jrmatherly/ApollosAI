from apollosai.server.config import ApollosAIServerConfig
from openhands.server.config.server_config import ServerConfig
from openhands.server.types import AppMode


def test_is_subclass_of_server_config():
    assert issubclass(ApollosAIServerConfig, ServerConfig)


def test_app_mode_is_saas():
    config = ApollosAIServerConfig()
    assert config.app_mode == AppMode.SAAS


def test_settings_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.settings_store_class


def test_user_auth_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.user_auth_class


def test_secret_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.secret_store_class


def test_conversation_store_class_points_to_apollosai():
    config = ApollosAIServerConfig()
    assert 'apollosai' in config.conversation_store_class


def test_enable_billing_is_false():
    config = ApollosAIServerConfig()
    assert config.enable_billing is False


def test_enable_v1_is_true():
    config = ApollosAIServerConfig()
    assert config.enable_v1 is True


def test_verify_config_raises_when_missing_env_vars(monkeypatch):
    """In production mode, missing env vars should raise ValueError."""
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', raising=False)
    monkeypatch.delenv('ENTRA_TENANT_ID', raising=False)
    monkeypatch.delenv('ENTRA_CLIENT_ID', raising=False)
    monkeypatch.delenv('JWT_SECRET', raising=False)
    config = ApollosAIServerConfig()
    import pytest

    with pytest.raises(ValueError, match='Missing required environment variables'):
        config.verify_config()


def test_verify_config_warns_in_dev_mode(monkeypatch):
    """In dev mode (APOLLOSAI_ALLOW_UNAUTHENTICATED=1), should warn not raise."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNAUTHENTICATED', '1')
    monkeypatch.delenv('ENTRA_TENANT_ID', raising=False)
    monkeypatch.delenv('ENTRA_CLIENT_ID', raising=False)
    monkeypatch.delenv('JWT_SECRET', raising=False)
    config = ApollosAIServerConfig()
    # Should not raise — just logs a warning
    config.verify_config()


def test_verify_config_passes_when_all_vars_set(monkeypatch):
    """No error when all required env vars are set."""
    monkeypatch.setenv('ENTRA_TENANT_ID', 'test-tenant')
    monkeypatch.setenv('ENTRA_CLIENT_ID', 'test-client')
    monkeypatch.setenv('JWT_SECRET', 'a' * 32)
    config = ApollosAIServerConfig()
    config.verify_config()

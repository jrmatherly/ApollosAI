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

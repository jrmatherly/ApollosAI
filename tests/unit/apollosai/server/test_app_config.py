from apollosai.server.app_config import create_apollosai_app_config
from openhands.app_server.config import AppServerConfig
from openhands.app_server.user.user_context import UserContextInjector


def test_returns_app_server_config():
    config = create_apollosai_app_config()
    assert isinstance(config, AppServerConfig)


def test_has_entra_user_injector():
    from apollosai.server.auth.user_context import EntraIDUserContextInjector

    config = create_apollosai_app_config()
    assert isinstance(config.user, EntraIDUserContextInjector)


def test_has_apollosai_lifespan():
    from apollosai.server.lifespan import ApollosAILifespanService

    config = create_apollosai_app_config()
    assert isinstance(config.lifespan, ApollosAILifespanService)

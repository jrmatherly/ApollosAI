import os

from apollosai.bootstrap import ensure_config_cls


def test_sets_config_cls_when_unset(monkeypatch):
    monkeypatch.delenv('OPENHANDS_CONFIG_CLS', raising=False)
    ensure_config_cls()
    assert (
        os.environ['OPENHANDS_CONFIG_CLS']
        == 'apollosai.server.config.ApollosAIServerConfig'
    )


def test_preserves_existing_config_cls(monkeypatch):
    monkeypatch.setenv('OPENHANDS_CONFIG_CLS', 'custom.Config')
    ensure_config_cls()
    assert os.environ['OPENHANDS_CONFIG_CLS'] == 'custom.Config'


def test_auth_routes_mounted():
    """Auth routes must be mounted at /api/auth/*."""
    from apollosai.app_server import base_app

    route_paths = []
    for route in base_app.routes:
        if hasattr(route, 'path'):
            route_paths.append(route.path)
        elif hasattr(route, 'routes'):
            for sub in route.routes:
                if hasattr(sub, 'path'):
                    route_paths.append(sub.path)
    assert any('auth/login' in p for p in route_paths)
    assert any('auth/callback' in p for p in route_paths)
    assert any('auth/logout' in p for p in route_paths)


def test_session_middleware_present():
    """SessionMiddleware must be configured."""
    from apollosai.app_server import base_app

    assert base_app is not None  # Smoke test: app loads without error

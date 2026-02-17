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

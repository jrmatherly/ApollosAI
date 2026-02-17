"""Config bootstrap — separated from app_server.py for testability."""

import os

APOLLOSAI_CONFIG_CLS = 'apollosai.server.config.ApollosAIServerConfig'


def ensure_config_cls() -> None:
    """Set OPENHANDS_CONFIG_CLS if not already set."""
    if not os.getenv('OPENHANDS_CONFIG_CLS'):
        os.environ['OPENHANDS_CONFIG_CLS'] = APOLLOSAI_CONFIG_CLS

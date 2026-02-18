"""Parametrized fail-closed tests for all integration managers (C2 regression protection)."""

import json

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.bitbucket.manager import BitbucketIntegrationManager
from apollosai.integrations.github.manager import GitHubIntegrationManager
from apollosai.integrations.jira.manager import JiraIntegrationManager
from apollosai.integrations.microsoft.manager import MicrosoftIntegrationManager
from apollosai.integrations.slack.manager import SlackIntegrationManager

MANAGERS = [
    GitHubIntegrationManager,
    JiraIntegrationManager,
    SlackIntegrationManager,
    BitbucketIntegrationManager,
    MicrosoftIntegrationManager,
]


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


@pytest.mark.parametrize('manager_cls', MANAGERS, ids=lambda c: c.__name__)
def test_no_secret_rejects_webhook(manager_cls, monkeypatch):
    """Managers without credentials must reject webhooks (fail closed)."""
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', raising=False)
    manager = manager_cls()
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=json.dumps({'type': 'event_callback'}).encode(),
        headers={'content-type': 'application/json'},
    )
    assert resp.status_code == 401, (
        f'{manager_cls.__name__} should reject when no secret configured'
    )


@pytest.mark.parametrize('manager_cls', MANAGERS, ids=lambda c: c.__name__)
def test_allow_unsigned_env_permits_webhook(manager_cls, monkeypatch):
    """APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true allows unsigned webhooks."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', 'true')
    manager = manager_cls()
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=json.dumps({
            'type': 'event_callback',
            'event': {
                'type': 'app_mention',
                'text': 'hi',
                'channel': 'C1',
                'ts': '1',
            },
        }).encode(),
        headers={'content-type': 'application/json'},
    )
    assert resp.status_code != 401, (
        f'{manager_cls.__name__} should allow when APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true'
    )

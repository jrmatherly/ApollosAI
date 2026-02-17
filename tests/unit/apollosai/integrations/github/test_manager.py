"""Tests for GitHub integration manager."""

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.github.manager import GitHubIntegrationManager
from apollosai.integrations.models import IntegrationType

WEBHOOK_SECRET = 'test-secret-key-for-github-webhooks'


def _sign_body(body: bytes, secret: str = WEBHOOK_SECRET) -> str:
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f'sha256={sig}'


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


# --- Webhook validation ---


def test_validate_webhook_valid_signature():
    manager = GitHubIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    payload = {'action': 'labeled', 'issue': {'number': 1, 'title': 'Test'}}
    body = json.dumps(payload).encode()
    sig = _sign_body(body)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=body,
        headers={'x-hub-signature-256': sig, 'content-type': 'application/json'},
    )
    # Event will be skipped (no matching label) but signature is valid
    assert resp.status_code == 200


def test_validate_webhook_invalid_signature():
    manager = GitHubIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        json={'action': 'opened'},
        headers={'x-hub-signature-256': 'sha256=invalid'},
    )
    assert resp.status_code == 401
    assert resp.json()['error'] == 'invalid_signature'


def test_validate_webhook_missing_signature():
    manager = GitHubIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={'action': 'opened'})
    assert resp.status_code == 401


def test_validate_webhook_no_secret_rejects(monkeypatch):
    """When no secret is configured, webhooks are rejected (fail-closed)."""
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', raising=False)
    manager = GitHubIntegrationManager(webhook_secret=None)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={'action': 'opened'})
    assert resp.status_code == 401


def test_validate_webhook_no_secret_with_env_override(monkeypatch):
    """APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true allows unsigned webhooks."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', 'true')
    manager = GitHubIntegrationManager(webhook_secret=None)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={'action': 'opened'})
    assert resp.status_code == 200
    assert resp.json()['status'] == 'skipped'


# --- Event parsing ---


@pytest.mark.asyncio
async def test_parse_issue_labeled_openhands():
    manager = GitHubIntegrationManager()
    payload = {
        'action': 'labeled',
        'label': {'name': 'openhands'},
        'issue': {
            'number': 42,
            'title': 'Bug report',
            'body': 'Something is broken',
            'html_url': 'https://github.com/org/repo/issues/42',
        },
        'repository': {'html_url': 'https://github.com/org/repo'},
        'sender': {'login': 'user', 'email': 'user@example.com'},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.source == IntegrationType.GITHUB
    assert event.event_type == 'issue_labeled'
    assert event.external_id == '42'
    assert event.title == 'Bug report'


@pytest.mark.asyncio
async def test_parse_issue_labeled_wrong_label():
    manager = GitHubIntegrationManager()
    payload = {
        'action': 'labeled',
        'label': {'name': 'bug'},
        'issue': {'number': 42, 'title': 'Bug report', 'html_url': 'url'},
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_issue_comment_with_mention():
    manager = GitHubIntegrationManager()
    payload = {
        'action': 'created',
        'comment': {
            'body': 'Hey @openhands please fix this',
            'html_url': 'https://github.com/org/repo/issues/42#issuecomment-1',
        },
        'issue': {
            'number': 42,
            'title': 'Bug report',
            'html_url': 'url',
        },
        'repository': {'html_url': 'https://github.com/org/repo'},
        'sender': {'login': 'user', 'email': None},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.event_type == 'issue_comment'
    assert event.body == 'Hey @openhands please fix this'


@pytest.mark.asyncio
async def test_parse_issue_comment_no_mention():
    manager = GitHubIntegrationManager()
    payload = {
        'action': 'created',
        'comment': {'body': 'Regular comment', 'html_url': 'url'},
        'issue': {'number': 42, 'title': 'Bug', 'html_url': 'url'},
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_unrecognized_event():
    manager = GitHubIntegrationManager()
    payload = {'action': 'opened', 'zen': 'Anything added dilutes everything else.'}
    event = await manager.parse_event(payload)
    assert event is None


# --- Context building ---


@pytest.mark.asyncio
async def test_build_context():
    from apollosai.integrations.models import IntegrationEvent

    manager = GitHubIntegrationManager()
    event = IntegrationEvent(
        source=IntegrationType.GITHUB,
        event_type='issue_labeled',
        external_id='42',
        title='Bug report',
        body='Fix the login page',
        repo_url='https://github.com/org/repo',
    )
    ctx = await manager.build_context(event)
    assert ctx.title == 'Bug report'
    assert ctx.initial_message == 'Fix the login page'
    assert ctx.repo_url == 'https://github.com/org/repo'
    assert ctx.metadata['source'] == 'github'

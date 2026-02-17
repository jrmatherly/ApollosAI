"""Tests for Bitbucket integration manager."""

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.bitbucket.manager import BitbucketIntegrationManager
from apollosai.integrations.models import IntegrationType

WEBHOOK_SECRET = 'bitbucket-test-webhook-secret'


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
    manager = BitbucketIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    payload = {'actor': {}, 'repository': {}}
    body = json.dumps(payload).encode()
    sig = _sign_body(body)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=body,
        headers={'content-type': 'application/json', 'x-hub-signature': sig},
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'skipped'


def test_validate_webhook_invalid_signature():
    manager = BitbucketIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        json={},
        headers={'x-hub-signature': 'sha256=invalid'},
    )
    assert resp.status_code == 401


def test_validate_webhook_missing_header():
    manager = BitbucketIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={})
    assert resp.status_code == 401


# --- Event parsing ---


@pytest.mark.asyncio
async def test_parse_pr_comment_with_mention():
    manager = BitbucketIntegrationManager()
    payload = {
        'pullrequest': {
            'id': 7,
            'title': 'Add feature X',
            'links': {'html': {'href': 'https://bitbucket.org/ws/repo/pull-requests/7'}},
        },
        'comment': {
            'id': 100,
            'content': {'raw': 'Hey @openhands please review this'},
        },
        'repository': {
            'full_name': 'ws/repo',
            'links': {'html': {'href': 'https://bitbucket.org/ws/repo'}},
        },
        'actor': {'nickname': 'alice'},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.source == IntegrationType.BITBUCKET
    assert event.event_type == 'pr_comment'
    assert event.external_id == '7'
    assert event.title == 'Add feature X'
    assert event.repo_url == 'https://bitbucket.org/ws/repo'


@pytest.mark.asyncio
async def test_parse_pr_comment_no_mention():
    manager = BitbucketIntegrationManager()
    payload = {
        'pullrequest': {'id': 7, 'title': 'PR'},
        'comment': {'id': 101, 'content': {'raw': 'LGTM'}},
        'repository': {'full_name': 'ws/repo'},
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_issue_comment_with_mention():
    manager = BitbucketIntegrationManager()
    payload = {
        'issue': {
            'id': 42,
            'title': 'Bug report',
            'links': {'html': {'href': 'https://bitbucket.org/ws/repo/issues/42'}},
        },
        'comment': {
            'id': 200,
            'content': {'raw': '@openhands fix this please'},
        },
        'repository': {
            'full_name': 'ws/repo',
            'links': {'html': {'href': 'https://bitbucket.org/ws/repo'}},
        },
        'actor': {'nickname': 'bob'},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.event_type == 'issue_comment'
    assert event.external_id == '42'


@pytest.mark.asyncio
async def test_parse_unrecognized_event():
    manager = BitbucketIntegrationManager()
    event = await manager.parse_event({'push': {'changes': []}})
    assert event is None


# --- Context building ---


@pytest.mark.asyncio
async def test_build_context():
    from apollosai.integrations.models import IntegrationEvent

    manager = BitbucketIntegrationManager()
    event = IntegrationEvent(
        source=IntegrationType.BITBUCKET,
        event_type='pr_comment',
        external_id='7',
        title='Add feature X',
        body='@openhands please review',
        repo_url='https://bitbucket.org/ws/repo',
    )
    ctx = await manager.build_context(event)
    assert ctx.title == 'Add feature X'
    assert ctx.repo_url == 'https://bitbucket.org/ws/repo'
    assert ctx.metadata['source'] == 'bitbucket'

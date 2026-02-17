"""Tests for Slack integration manager."""

import hashlib
import hmac
import json
import time

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.models import IntegrationType
from apollosai.integrations.slack.manager import SlackIntegrationManager

SIGNING_SECRET = 'slack-test-signing-secret'


def _sign_request(body: bytes, timestamp: int, secret: str = SIGNING_SECRET) -> str:
    basestring = f'v0:{timestamp}:{body.decode()}'.encode()
    sig = hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f'v0={sig}'


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


# --- URL verification ---


def test_url_verification_challenge():
    """Slack url_verification should be echoed after signature validation."""
    manager = SlackIntegrationManager(signing_secret=SIGNING_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    payload = json.dumps({'type': 'url_verification', 'challenge': 'abc123'}).encode()
    ts = int(time.time())
    sig = _sign_request(payload, ts)
    resp = client.post(
        '/webhook',
        content=payload,
        headers={
            'content-type': 'application/json',
            'x-slack-request-timestamp': str(ts),
            'x-slack-signature': sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json()['challenge'] == 'abc123'


def test_url_verification_requires_valid_signature():
    """url_verification with invalid/missing signature should be rejected."""
    manager = SlackIntegrationManager(signing_secret=SIGNING_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    # Send url_verification with no signature headers
    resp = client.post(
        '/webhook', json={'type': 'url_verification', 'challenge': 'abc'}
    )
    assert resp.status_code == 401, (
        'url_verification should be rejected without valid signature'
    )


# --- Webhook validation ---


def test_validate_webhook_valid_signature():
    manager = SlackIntegrationManager(signing_secret=SIGNING_SECRET)
    payload = {
        'type': 'event_callback',
        'event': {
            'type': 'app_mention',
            'text': 'Hello bot',
            'channel': 'C123',
            'ts': '1234567890.123456',
        },
    }
    body = json.dumps(payload).encode()
    ts = int(time.time())
    sig = _sign_request(body, ts)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        content=body,
        headers={
            'content-type': 'application/json',
            'x-slack-request-timestamp': str(ts),
            'x-slack-signature': sig,
        },
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'processed'


def test_validate_webhook_invalid_signature():
    manager = SlackIntegrationManager(signing_secret=SIGNING_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    ts = int(time.time())
    resp = client.post(
        '/webhook',
        content=b'{"type":"event_callback"}',
        headers={
            'content-type': 'application/json',
            'x-slack-request-timestamp': str(ts),
            'x-slack-signature': 'v0=invalid',
        },
    )
    assert resp.status_code == 401


def test_validate_webhook_replay_protection(monkeypatch):
    """Requests older than 5 minutes should be rejected."""
    manager = SlackIntegrationManager(signing_secret=SIGNING_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    old_ts = int(time.time()) - 600  # 10 minutes ago
    body = b'{"type":"event_callback"}'
    sig = _sign_request(body, old_ts)
    resp = client.post(
        '/webhook',
        content=body,
        headers={
            'content-type': 'application/json',
            'x-slack-request-timestamp': str(old_ts),
            'x-slack-signature': sig,
        },
    )
    assert resp.status_code == 401


# --- Event parsing ---


@pytest.mark.asyncio
async def test_parse_app_mention():
    manager = SlackIntegrationManager()
    payload = {
        'type': 'event_callback',
        'event': {
            'type': 'app_mention',
            'text': '<@U123> fix the bug please',
            'channel': 'C456',
            'ts': '1234.5678',
        },
        'team_id': 'T789',
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.source == IntegrationType.SLACK
    assert event.event_type == 'app_mention'
    assert event.external_id == '1234.5678'
    assert 'fix the bug' in event.body


@pytest.mark.asyncio
async def test_parse_direct_message():
    manager = SlackIntegrationManager()
    payload = {
        'type': 'event_callback',
        'event': {
            'type': 'message',
            'channel_type': 'im',
            'text': 'Hello bot',
            'ts': '1234.5678',
        },
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.event_type == 'direct_message'


@pytest.mark.asyncio
async def test_parse_bot_message_ignored():
    """Bot's own messages should be ignored."""
    manager = SlackIntegrationManager()
    payload = {
        'type': 'event_callback',
        'event': {
            'type': 'message',
            'channel_type': 'im',
            'text': 'Bot reply',
            'bot_id': 'B123',
            'ts': '1234.5678',
        },
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_irrelevant_event():
    manager = SlackIntegrationManager()
    payload = {
        'type': 'event_callback',
        'event': {
            'type': 'channel_created',
            'channel': {'id': 'C123'},
        },
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_non_event_callback():
    manager = SlackIntegrationManager()
    event = await manager.parse_event({'type': 'url_verification'})
    assert event is None


# --- Context building ---


@pytest.mark.asyncio
async def test_build_context():
    from apollosai.integrations.models import IntegrationEvent

    manager = SlackIntegrationManager()
    event = IntegrationEvent(
        source=IntegrationType.SLACK,
        event_type='app_mention',
        external_id='1234.5678',
        title='Slack mention in #general',
        body='<@U123> fix the login page',
    )
    ctx = await manager.build_context(event)
    assert ctx.title == 'Slack mention in #general'
    assert 'fix the login page' in ctx.initial_message
    assert ctx.metadata['source'] == 'slack'

"""Tests for Microsoft 365 integration manager."""

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.microsoft.manager import MicrosoftIntegrationManager
from apollosai.integrations.microsoft.mcp_tools import (
    MICROSOFT_MCP_TOOLS,
)
from apollosai.integrations.models import IntegrationType

CLIENT_STATE = 'test-client-state-secret'


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


# --- Subscription validation ---


def test_graph_validation_token_echo():
    """Graph subscription validation: echo the validationToken as plain text."""
    manager = MicrosoftIntegrationManager(client_state=CLIENT_STATE)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook?validationToken=abc123')
    assert resp.status_code == 200
    assert resp.text == 'abc123'
    assert 'text/plain' in resp.headers['content-type']


# --- Webhook validation ---


def test_validate_webhook_valid_client_state():
    manager = MicrosoftIntegrationManager(client_state=CLIENT_STATE)
    payload = {
        'value': [
            {
                'clientState': CLIENT_STATE,
                'changeType': 'created',
                'resource': 'me/messages/123',
                'resourceData': {'id': '123'},
            }
        ]
    }
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json=payload)
    assert resp.status_code == 200
    assert resp.json()['status'] == 'processed'


def test_validate_webhook_invalid_client_state():
    manager = MicrosoftIntegrationManager(client_state=CLIENT_STATE)
    payload = {
        'value': [
            {
                'clientState': 'wrong-state',
                'changeType': 'created',
                'resource': 'me/messages/123',
            }
        ]
    }
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json=payload)
    assert resp.status_code == 401


def test_validation_token_in_body_does_not_bypass_client_state():
    """A validationToken in the JSON body must NOT bypass client_state check (C4)."""
    manager = MicrosoftIntegrationManager(client_state=CLIENT_STATE)
    payload = {
        'validationToken': 'sneaky',
        'value': [
            {
                'clientState': 'wrong-state',
                'changeType': 'created',
                'resource': 'me/messages/123',
            }
        ],
    }
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json=payload)
    assert resp.status_code == 401


def test_validate_webhook_no_client_state_rejects(monkeypatch):
    """When no client state is configured, webhooks are rejected (fail-closed)."""
    monkeypatch.delenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', raising=False)
    manager = MicrosoftIntegrationManager(client_state=None)
    payload = {'value': []}
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json=payload)
    assert resp.status_code == 401


def test_validate_webhook_no_client_state_with_env_override(monkeypatch):
    """APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS=true allows unsigned webhooks."""
    monkeypatch.setenv('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', 'true')
    manager = MicrosoftIntegrationManager(client_state=None)
    payload = {'value': []}
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json=payload)
    assert resp.status_code == 200


# --- Event parsing ---


@pytest.mark.asyncio
async def test_parse_change_notification():
    manager = MicrosoftIntegrationManager()
    payload = {
        'value': [
            {
                'changeType': 'created',
                'resource': 'me/messages/abc',
                'resourceData': {'id': 'abc'},
                'clientState': '',
            }
        ]
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.source == IntegrationType.MICROSOFT
    assert event.event_type == 'graph_created'
    assert event.external_id == 'abc'


@pytest.mark.asyncio
async def test_parse_empty_notifications():
    manager = MicrosoftIntegrationManager()
    event = await manager.parse_event({'value': []})
    assert event is None


@pytest.mark.asyncio
async def test_parse_no_resource():
    manager = MicrosoftIntegrationManager()
    event = await manager.parse_event({'value': [{'changeType': 'updated'}]})
    assert event is None


# --- Context building ---


@pytest.mark.asyncio
async def test_build_context():
    from apollosai.integrations.models import IntegrationEvent

    manager = MicrosoftIntegrationManager()
    event = IntegrationEvent(
        source=IntegrationType.MICROSOFT,
        event_type='graph_created',
        external_id='abc',
        title='Graph created: me/messages/abc',
    )
    ctx = await manager.build_context(event)
    assert 'Graph created' in ctx.title
    assert ctx.metadata['source'] == 'microsoft'


# --- OAuth config ---


def test_get_oauth_config():
    manager = MicrosoftIntegrationManager(
        tenant_id='test-tenant',
        client_id='test-client',
    )
    config = manager.get_oauth_config()
    assert config is not None
    assert 'test-tenant' in config.authorize_url
    assert config.client_id == 'test-client'


def test_get_oauth_config_none_without_ids():
    manager = MicrosoftIntegrationManager()
    assert manager.get_oauth_config() is None


# --- MCP tools ---


def test_mcp_tools_defined():
    assert len(MICROSOFT_MCP_TOOLS) == 3
    names = [t['name'] for t in MICROSOFT_MCP_TOOLS]
    assert 'microsoft_search_documents' in names
    assert 'microsoft_read_file' in names
    assert 'microsoft_list_emails' in names

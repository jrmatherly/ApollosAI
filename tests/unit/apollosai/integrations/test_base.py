"""Tests for ApollosAIIntegrationManager base class."""

import pytest
from starlette.testclient import TestClient

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)


class ConcreteManager(ApollosAIIntegrationManager):
    """Test implementation of the abstract base manager."""

    source_type = IntegrationType.GITHUB

    def __init__(self, *, valid=True, event=None, context=None):
        self._valid = valid
        self._event = event
        self._context = context
        self.calls: list[str] = []

    async def validate_webhook(self, request):
        self.calls.append('validate_webhook')
        return self._valid

    async def parse_event(self, payload):
        self.calls.append('parse_event')
        return self._event

    async def build_context(self, event):
        self.calls.append('build_context')
        return self._context

    async def post_response(self, conversation_id, message):
        self.calls.append('post_response')


def _make_app(manager):
    """Create a FastAPI app with a webhook endpoint backed by the given manager."""
    from fastapi import FastAPI, Request

    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


def test_abc_enforcement():
    """Cannot instantiate without implementing all abstract methods."""
    with pytest.raises(TypeError):
        ApollosAIIntegrationManager()


def test_handle_webhook_invalid_signature():
    manager = ConcreteManager(valid=False)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={})
    assert resp.status_code == 401
    assert resp.json()['error'] == 'invalid_signature'
    assert manager.calls == ['validate_webhook']


def test_handle_webhook_skip_event():
    manager = ConcreteManager(valid=True, event=None)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={'action': 'irrelevant'})
    assert resp.status_code == 200
    assert resp.json()['status'] == 'skipped'
    assert manager.calls == ['validate_webhook', 'parse_event']


def test_handle_webhook_full_pipeline():
    event = IntegrationEvent(
        source=IntegrationType.GITHUB,
        event_type='issues',
        external_id='42',
    )
    context = ConversationContext(
        title='Fix issue #42',
        initial_message='Please fix the bug',
    )
    manager = ConcreteManager(valid=True, event=event, context=context)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={'action': 'opened'})
    assert resp.status_code == 200
    data = resp.json()
    assert data['status'] == 'processed'
    assert data['title'] == 'Fix issue #42'
    assert manager.calls == ['validate_webhook', 'parse_event', 'build_context']


def test_handle_webhook_unsupported_content_type():
    manager = ConcreteManager(valid=True)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook', content=b'plain', headers={'content-type': 'text/plain'}
    )
    assert resp.status_code == 400
    assert resp.json()['error'] == 'unsupported_content_type'


def test_get_oauth_config_default_none():
    manager = ConcreteManager()
    assert manager.get_oauth_config() is None

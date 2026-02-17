"""Tests for integration registry and generic routes."""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)
from apollosai.integrations.registry import (
    clear_registry,
    get_integration,
    list_integrations,
    register_integration,
)

# --- Registry unit tests ---


class _StubManager(ApollosAIIntegrationManager):
    source_type = IntegrationType.GITHUB

    async def validate_webhook(self, request):
        return True

    async def parse_event(self, payload):
        return IntegrationEvent(
            source=IntegrationType.GITHUB,
            event_type='test',
            external_id='1',
        )

    async def build_context(self, event):
        return ConversationContext(title='Test', initial_message='msg')

    async def post_response(self, conversation_id, message):
        pass


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def test_register_and_get():
    register_integration(IntegrationType.GITHUB, _StubManager)
    assert get_integration(IntegrationType.GITHUB) is _StubManager


def test_get_unregistered_returns_none():
    assert get_integration(IntegrationType.JIRA) is None


def test_list_integrations():
    register_integration(IntegrationType.GITHUB, _StubManager)
    assert IntegrationType.GITHUB in list_integrations()


# --- Route tests ---


def _make_app():
    from apollosai.server.routes.integrations import router

    app = FastAPI()
    app.include_router(router)
    return app


def test_webhook_unknown_integration():
    app = _make_app()
    client = TestClient(app)
    resp = client.post('/api/webhooks/unknown', json={})
    assert resp.status_code == 404
    assert 'Unknown integration' in resp.json()['error']


def test_webhook_not_registered():
    app = _make_app()
    client = TestClient(app)
    resp = client.post('/api/webhooks/github', json={})
    assert resp.status_code == 404
    assert 'not registered' in resp.json()['error']


def test_webhook_success():
    register_integration(IntegrationType.GITHUB, _StubManager)
    app = _make_app()
    client = TestClient(app)
    resp = client.post('/api/webhooks/github', json={'action': 'opened'})
    assert resp.status_code == 200
    assert resp.json()['status'] == 'processed'

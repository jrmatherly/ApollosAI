"""Tests for replay protection (M1) and payload sanitization (M5)."""

import pytest
from starlette.testclient import TestClient

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
    sanitize_payload,
)


class ReplayTestManager(ApollosAIIntegrationManager):
    """Concrete manager for testing replay protection."""

    __test__ = False

    source_type = IntegrationType.GITHUB

    def __init__(self):
        # Each instance gets its own dedup cache to isolate tests
        self._seen_events = type(self._seen_events)()

    async def validate_webhook(self, request):
        return True

    async def parse_event(self, payload):
        if not payload.get('id'):
            return None
        return IntegrationEvent(
            source=IntegrationType.GITHUB,
            event_type='test',
            external_id=payload['id'],
            raw_payload=payload,
        )

    async def build_context(self, event):
        return ConversationContext(
            title=f'Event {event.external_id}',
            initial_message='test',
        )

    async def post_response(self, conversation_id, message):
        pass


def _make_app(manager):
    from fastapi import FastAPI, Request

    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


class TestReplayProtection:
    """M1: Duplicate event detection via external_id dedup cache."""

    def test_first_event_accepted(self):
        manager = ReplayTestManager()
        app = _make_app(manager)
        client = TestClient(app)
        resp = client.post('/webhook', json={'id': 'evt-1'})
        assert resp.json()['status'] == 'processed'

    def test_duplicate_event_rejected(self):
        manager = ReplayTestManager()
        app = _make_app(manager)
        client = TestClient(app)
        client.post('/webhook', json={'id': 'evt-1'})
        resp = client.post('/webhook', json={'id': 'evt-1'})
        assert resp.json()['status'] == 'duplicate'

    def test_different_ids_both_accepted(self):
        manager = ReplayTestManager()
        app = _make_app(manager)
        client = TestClient(app)
        resp1 = client.post('/webhook', json={'id': 'evt-1'})
        resp2 = client.post('/webhook', json={'id': 'evt-2'})
        assert resp1.json()['status'] == 'processed'
        assert resp2.json()['status'] == 'processed'

    def test_skipped_events_not_tracked(self):
        """Events that parse_event returns None for should not be tracked."""
        manager = ReplayTestManager()
        app = _make_app(manager)
        client = TestClient(app)
        resp = client.post('/webhook', json={'no_id': True})
        assert resp.json()['status'] == 'skipped'
        assert len(manager._seen_events) == 0

    def test_eviction_at_max_size(self):
        """Oldest entries are evicted when cache exceeds _MAX_SEEN."""
        manager = ReplayTestManager()
        manager._MAX_SEEN = 5

        for i in range(7):
            assert not manager._check_replay(f'evt-{i}')

        # First two should have been evicted
        assert not manager._check_replay('evt-0')
        assert not manager._check_replay('evt-1')
        # Recent ones should still be there
        assert manager._check_replay('evt-5')
        assert manager._check_replay('evt-6')

    def test_check_replay_direct(self):
        """Direct unit test of _check_replay method."""
        manager = ReplayTestManager()
        assert not manager._check_replay('x')
        assert manager._check_replay('x')
        assert not manager._check_replay('y')


class TestPayloadSanitization:
    """M5: Sensitive fields stripped from raw_payload before storage."""

    def test_top_level_keys_redacted(self):
        payload = {'action': 'opened', 'token': 'ghp_secret123', 'data': 'safe'}
        result = sanitize_payload(payload)
        assert result['action'] == 'opened'
        assert result['token'] == '[REDACTED]'
        assert result['data'] == 'safe'

    def test_nested_keys_redacted(self):
        payload = {
            'repository': {
                'name': 'repo',
                'access_token': 'tok-abc',
            }
        }
        result = sanitize_payload(payload)
        assert result['repository']['name'] == 'repo'
        assert result['repository']['access_token'] == '[REDACTED]'

    def test_list_of_dicts_sanitized(self):
        payload = {
            'items': [
                {'name': 'a', 'secret': 'hidden'},
                {'name': 'b', 'value': 'safe'},
            ]
        }
        result = sanitize_payload(payload)
        assert result['items'][0]['secret'] == '[REDACTED]'
        assert result['items'][1]['value'] == 'safe'

    def test_case_insensitive_matching(self):
        payload = {'Token': 'val', 'PASSWORD': 'val', 'Api_Key': 'val'}
        result = sanitize_payload(payload)
        assert result['Token'] == '[REDACTED]'
        assert result['PASSWORD'] == '[REDACTED]'
        assert result['Api_Key'] == '[REDACTED]'

    def test_non_sensitive_keys_preserved(self):
        payload = {'action': 'opened', 'issue': {'number': 42}, 'labels': ['bug']}
        result = sanitize_payload(payload)
        assert result == payload

    def test_empty_payload(self):
        assert sanitize_payload({}) == {}

    def test_deeply_nested(self):
        payload = {
            'l1': {
                'l2': {
                    'l3': {
                        'client_secret': 'deep-secret',
                        'data': 'safe',
                    }
                }
            }
        }
        result = sanitize_payload(payload)
        assert result['l1']['l2']['l3']['client_secret'] == '[REDACTED]'
        assert result['l1']['l2']['l3']['data'] == 'safe'

    def test_integration_event_auto_sanitizes(self):
        """IntegrationEvent model_validator automatically sanitizes raw_payload."""
        event = IntegrationEvent(
            source=IntegrationType.GITHUB,
            event_type='test',
            external_id='1',
            raw_payload={'action': 'opened', 'token': 'ghp_secret'},
        )
        assert event.raw_payload['action'] == 'opened'
        assert event.raw_payload['token'] == '[REDACTED]'

    def test_integration_event_none_payload_ok(self):
        """IntegrationEvent with no raw_payload should not fail."""
        event = IntegrationEvent(
            source=IntegrationType.GITHUB,
            event_type='test',
            external_id='1',
        )
        assert event.raw_payload is None

    @pytest.mark.parametrize(
        'key',
        [
            'token',
            'secret',
            'password',
            'authorization',
            'api_key',
            'access_token',
            'refresh_token',
            'client_secret',
        ],
    )
    def test_all_sensitive_keys(self, key):
        """Each sensitive key in the set is properly redacted."""
        payload = {key: 'sensitive-value', 'safe_key': 'safe-value'}
        result = sanitize_payload(payload)
        assert result[key] == '[REDACTED]'
        assert result['safe_key'] == 'safe-value'

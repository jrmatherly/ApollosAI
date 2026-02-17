"""Tests for Jira integration manager."""

import pytest
from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from apollosai.integrations.jira.manager import (
    JiraIntegrationManager,
    _extract_adf_text,
)
from apollosai.integrations.models import IntegrationType

WEBHOOK_SECRET = 'jira-test-webhook-secret'


def _make_app(manager):
    app = FastAPI()

    @app.post('/webhook')
    async def webhook(request: Request):
        return await manager.handle_webhook(request)

    return app


# --- Webhook validation ---


def test_validate_webhook_valid_token():
    manager = JiraIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        json={'webhookEvent': 'unknown'},
        headers={'x-atlassian-webhook-identifier': WEBHOOK_SECRET},
    )
    assert resp.status_code == 200
    assert resp.json()['status'] == 'skipped'


def test_validate_webhook_invalid_token():
    manager = JiraIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post(
        '/webhook',
        json={},
        headers={'x-atlassian-webhook-identifier': 'wrong-secret'},
    )
    assert resp.status_code == 401


def test_validate_webhook_missing_header():
    manager = JiraIntegrationManager(webhook_secret=WEBHOOK_SECRET)
    app = _make_app(manager)
    client = TestClient(app)
    resp = client.post('/webhook', json={})
    assert resp.status_code == 401


# --- Event parsing ---


@pytest.mark.asyncio
async def test_parse_issue_created_with_label():
    manager = JiraIntegrationManager(base_url='https://jira.example.com')
    payload = {
        'webhookEvent': 'jira:issue_created',
        'issue': {
            'key': 'PROJ-42',
            'fields': {
                'summary': 'Fix the bug',
                'description': 'Something is wrong',
                'labels': ['openhands', 'bug'],
            },
        },
        'user': {'emailAddress': 'user@example.com'},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.source == IntegrationType.JIRA
    assert event.event_type == 'issue_created'
    assert event.external_id == 'PROJ-42'
    assert event.title == 'Fix the bug'
    assert event.external_url == 'https://jira.example.com/browse/PROJ-42'


@pytest.mark.asyncio
async def test_parse_issue_created_without_label():
    manager = JiraIntegrationManager()
    payload = {
        'webhookEvent': 'jira:issue_created',
        'issue': {
            'key': 'PROJ-43',
            'fields': {
                'summary': 'No trigger label',
                'labels': ['bug'],
            },
        },
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_issue_updated_label_added():
    manager = JiraIntegrationManager()
    payload = {
        'webhookEvent': 'jira:issue_updated',
        'issue': {
            'key': 'PROJ-44',
            'fields': {'summary': 'Updated issue'},
        },
        'changelog': {
            'items': [
                {
                    'field': 'labels',
                    'fromString': 'bug',
                    'toString': 'bug openhands',
                }
            ]
        },
        'user': {'emailAddress': 'user@example.com'},
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.event_type == 'issue_labeled'


@pytest.mark.asyncio
async def test_parse_comment_with_mention():
    manager = JiraIntegrationManager()
    payload = {
        'webhookEvent': 'comment_created',
        'issue': {
            'key': 'PROJ-45',
            'fields': {'summary': 'Issue with comment'},
        },
        'comment': {
            'body': 'Hey @openhands please help',
            'author': {'emailAddress': 'commenter@example.com'},
        },
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert event.event_type == 'comment_created'
    assert event.body == 'Hey @openhands please help'


@pytest.mark.asyncio
async def test_parse_comment_adf_format():
    """Jira Cloud sends comments in ADF format."""
    manager = JiraIntegrationManager()
    payload = {
        'webhookEvent': 'comment_created',
        'issue': {
            'key': 'PROJ-46',
            'fields': {'summary': 'ADF comment test'},
        },
        'comment': {
            'body': {
                'type': 'doc',
                'version': 1,
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [
                            {'type': 'text', 'text': 'Hey '},
                            {'type': 'text', 'text': '@openhands fix this'},
                        ],
                    }
                ],
            },
            'author': {'emailAddress': 'user@example.com'},
        },
    }
    event = await manager.parse_event(payload)
    assert event is not None
    assert '@openhands' in event.body


@pytest.mark.asyncio
async def test_parse_comment_no_mention():
    manager = JiraIntegrationManager()
    payload = {
        'webhookEvent': 'comment_created',
        'issue': {
            'key': 'PROJ-47',
            'fields': {'summary': 'Regular comment'},
        },
        'comment': {
            'body': 'Just a regular comment',
            'author': {},
        },
    }
    event = await manager.parse_event(payload)
    assert event is None


@pytest.mark.asyncio
async def test_parse_unknown_event():
    manager = JiraIntegrationManager()
    event = await manager.parse_event({'webhookEvent': 'project_updated'})
    assert event is None


# --- ADF extraction ---


def test_extract_adf_text():
    adf = {
        'type': 'doc',
        'content': [
            {
                'type': 'paragraph',
                'content': [
                    {'type': 'text', 'text': 'Hello '},
                    {'type': 'text', 'text': 'world'},
                ],
            }
        ],
    }
    assert _extract_adf_text(adf) == 'Hello world'


# --- Context building ---


@pytest.mark.asyncio
async def test_build_context():
    from apollosai.integrations.models import IntegrationEvent

    manager = JiraIntegrationManager()
    event = IntegrationEvent(
        source=IntegrationType.JIRA,
        event_type='issue_created',
        external_id='PROJ-42',
        title='Fix the bug',
        body='Description text',
    )
    ctx = await manager.build_context(event)
    assert ctx.title == 'Fix the bug'
    assert ctx.initial_message == 'Description text'
    assert ctx.metadata['source'] == 'jira'

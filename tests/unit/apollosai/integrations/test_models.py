"""Tests for integration framework Pydantic models."""

from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
    OAuthConfig,
)


def test_integration_event_minimal():
    event = IntegrationEvent(
        source=IntegrationType.GITHUB,
        event_type='issue_opened',
        external_id='123',
    )
    assert event.source == IntegrationType.GITHUB
    assert event.event_type == 'issue_opened'
    assert event.external_id == '123'
    assert event.external_url is None
    assert event.raw_payload is None


def test_integration_event_full():
    event = IntegrationEvent(
        source=IntegrationType.JIRA,
        event_type='issue_created',
        external_id='PROJ-42',
        external_url='https://jira.example.com/browse/PROJ-42',
        title='Fix bug',
        body='Description here',
        repo_url='https://github.com/org/repo',
        user_email='user@example.com',
        raw_payload={'key': 'value'},
    )
    assert event.source == IntegrationType.JIRA
    assert event.title == 'Fix bug'
    assert event.raw_payload == {'key': 'value'}


def test_conversation_context():
    ctx = ConversationContext(
        title='Fix issue #42',
        initial_message='Please fix the login bug',
        repo_url='https://github.com/org/repo',
        metadata={'issue_id': '42'},
    )
    assert ctx.title == 'Fix issue #42'
    assert ctx.metadata == {'issue_id': '42'}


def test_oauth_config():
    config = OAuthConfig(
        authorize_url='https://auth.example.com/authorize',
        token_url='https://auth.example.com/token',
        client_id='client123',
        scopes=['read', 'write'],
    )
    assert config.client_id == 'client123'
    assert len(config.scopes) == 2


def test_integration_type_values():
    """Verify IntegrationType enum has expected values."""
    assert IntegrationType.GITHUB.value == 'github'
    assert IntegrationType.JIRA.value == 'jira'
    assert IntegrationType.SLACK.value == 'slack'

"""Jira integration manager for ApollosAI."""

import hmac
import logging

from fastapi import Request

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)

logger = logging.getLogger(__name__)

# Jira Cloud webhook event types we process
TRIGGER_LABEL = 'openhands'


class JiraIntegrationManager(ApollosAIIntegrationManager):
    """Handles Jira Cloud webhooks for issues and comments."""

    source_type = IntegrationType.JIRA

    def __init__(
        self,
        webhook_secret: str | None = None,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
    ):
        self._webhook_secret = webhook_secret
        self._base_url = base_url
        self._email = email
        self._api_token = api_token

    async def validate_webhook(self, request: Request) -> bool:
        """Validate Jira webhook using shared secret in header.

        Jira Cloud sends the webhook secret as a token in a custom header.
        """
        if self._webhook_secret is None:
            logger.warning('No webhook secret configured — skipping validation')
            return True

        token = request.headers.get('x-atlassian-webhook-identifier')
        if not token:
            return False

        return hmac.compare_digest(token, self._webhook_secret)

    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse Jira webhook payload into an IntegrationEvent."""
        webhook_event = payload.get('webhookEvent', '')
        issue_data = payload.get('issue', {})
        fields = issue_data.get('fields', {})

        if not issue_data:
            return None

        issue_key = issue_data.get('key', '')
        jira_url = self._base_url or ''
        external_url = f'{jira_url}/browse/{issue_key}' if jira_url else None

        # Issue created with trigger label
        if webhook_event == 'jira:issue_created':
            labels = [
                lbl.get('name', '') if isinstance(lbl, dict) else lbl
                for lbl in fields.get('labels', [])
            ]
            if TRIGGER_LABEL not in [lbl.lower() for lbl in labels]:
                return None
            user = payload.get('user', {})
            return IntegrationEvent(
                source=IntegrationType.JIRA,
                event_type='issue_created',
                external_id=issue_key,
                external_url=external_url,
                title=fields.get('summary'),
                body=fields.get('description'),
                user_email=user.get('emailAddress'),
                raw_payload=payload,
            )

        # Issue updated — label added
        if webhook_event == 'jira:issue_updated':
            changelog = payload.get('changelog', {})
            for item in changelog.get('items', []):
                if item.get('field') == 'labels' and TRIGGER_LABEL in (
                    item.get('toString', '').lower()
                ):
                    user = payload.get('user', {})
                    return IntegrationEvent(
                        source=IntegrationType.JIRA,
                        event_type='issue_labeled',
                        external_id=issue_key,
                        external_url=external_url,
                        title=fields.get('summary'),
                        body=fields.get('description'),
                        user_email=user.get('emailAddress'),
                        raw_payload=payload,
                    )
            return None

        # Comment created with @openhands mention
        if webhook_event == 'comment_created':
            comment = payload.get('comment', {})
            comment_body = comment.get('body', '')
            if isinstance(comment_body, dict):
                # ADF format — extract text from content nodes
                comment_body = _extract_adf_text(comment_body)
            if '@openhands' not in comment_body.lower():
                return None
            user = comment.get('author', {})
            return IntegrationEvent(
                source=IntegrationType.JIRA,
                event_type='comment_created',
                external_id=issue_key,
                external_url=external_url,
                title=fields.get('summary'),
                body=comment_body,
                user_email=user.get('emailAddress'),
                raw_payload=payload,
            )

        return None

    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a Jira event."""
        title = event.title or f'Jira {event.event_type} {event.external_id}'
        message = event.body or title
        return ConversationContext(
            title=title,
            initial_message=message,
            metadata={
                'source': 'jira',
                'event_type': event.event_type,
                'external_id': event.external_id,
                'external_url': event.external_url,
            },
        )

    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response comment back to Jira."""
        if not all([self._base_url, self._email, self._api_token]):
            logger.warning('Jira credentials not configured — cannot post response')
            return
        from apollosai.integrations.jira.service import JiraService

        service = JiraService(self._base_url, self._email, self._api_token)
        # conversation_id is the Jira issue key (e.g., "PROJ-42")
        await service.post_comment(conversation_id, message)


def _extract_adf_text(adf: dict) -> str:
    """Recursively extract plain text from Atlassian Document Format."""
    parts: list[str] = []
    if adf.get('type') == 'text':
        parts.append(adf.get('text', ''))
    for child in adf.get('content', []):
        parts.append(_extract_adf_text(child))
    return ''.join(parts)

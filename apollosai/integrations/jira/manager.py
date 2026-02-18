"""Jira integration manager for ApollosAI."""

import hmac
import logging
import os

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
            if os.environ.get('APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS', '').lower() in (
                '1',
                'true',
                'yes',
            ):
                logger.warning(
                    'Unsigned webhook accepted — APOLLOSAI_ALLOW_UNSIGNED_WEBHOOKS is set'
                )
                return True
            logger.error(
                'No webhook secret configured — rejecting request (fail-closed)'
            )
            return False

        token = request.headers.get('x-atlassian-webhook-identifier')
        if not token:
            return False

        return hmac.compare_digest(token, self._webhook_secret)

    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse Jira webhook payload into an IntegrationEvent.

        Uses typed views for structural validation (H9).
        Jira payloads use camelCase keys (e.g. webhookEvent) that don't map
        cleanly to Pydantic field names, so we keep dict access for the
        top-level routing while using views models for nested structures.
        """
        from apollosai.integrations.jira.views import JiraWebhookPayload

        typed = JiraWebhookPayload.model_validate(payload)

        webhook_event = payload.get('webhookEvent', '')
        if not typed.issue:
            return None

        issue_key = typed.issue.key
        jira_url = self._base_url or ''
        external_url = f'{jira_url}/browse/{issue_key}' if jira_url else None

        # Issue created with trigger label
        if webhook_event == 'jira:issue_created':
            labels = [
                lbl.get('name', '') if isinstance(lbl, dict) else lbl
                for lbl in typed.issue.fields.labels
            ]
            if TRIGGER_LABEL not in [lbl.lower() for lbl in labels]:
                return None
            user = typed.user
            return IntegrationEvent(
                source=IntegrationType.JIRA,
                event_type='issue_created',
                external_id=issue_key,
                external_url=external_url,
                title=typed.issue.fields.summary,
                body=typed.issue.fields.description,
                user_email=user.email_address if user else None,
                raw_payload=payload,
            )

        # Issue updated — label added
        if webhook_event == 'jira:issue_updated':
            changelog = typed.changelog
            if changelog:
                for item in changelog.items:
                    if item.get('field') == 'labels' and TRIGGER_LABEL in (
                        item.get('toString', '').lower()
                    ):
                        user = typed.user
                        return IntegrationEvent(
                            source=IntegrationType.JIRA,
                            event_type='issue_labeled',
                            external_id=issue_key,
                            external_url=external_url,
                            title=typed.issue.fields.summary,
                            body=typed.issue.fields.description,
                            user_email=user.email_address if user else None,
                            raw_payload=payload,
                        )
            return None

        # Comment created with @openhands mention
        if webhook_event == 'comment_created':
            comment = typed.comment
            comment_body = comment.body if comment else ''
            if isinstance(comment_body, dict):
                # ADF format — extract text from content nodes
                comment_body = _extract_adf_text(comment_body)
            if not comment_body or '@openhands' not in comment_body.lower():
                return None
            author = comment.author if comment else None
            return IntegrationEvent(
                source=IntegrationType.JIRA,
                event_type='comment_created',
                external_id=issue_key,
                external_url=external_url,
                title=typed.issue.fields.summary,
                body=comment_body,
                user_email=author.email_address if author else None,
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

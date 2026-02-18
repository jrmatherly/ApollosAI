"""GitHub integration manager for ApollosAI."""

import hashlib
import hmac
import logging
import os

from fastapi import Request

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.github.views import GitHubWebhookPayload
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)

logger = logging.getLogger(__name__)


class GitHubIntegrationManager(ApollosAIIntegrationManager):
    """Handles GitHub webhooks for issues, comments, and PRs."""

    source_type = IntegrationType.GITHUB

    # Events we care about
    SUPPORTED_EVENTS = {'issues', 'issue_comment', 'pull_request_review_comment'}

    def __init__(self, webhook_secret: str | None = None, api_token: str | None = None):
        self._webhook_secret = webhook_secret
        self._api_token = api_token

    async def validate_webhook(self, request: Request) -> bool:
        """Validate GitHub webhook using HMAC-SHA256 signature."""
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

        signature = request.headers.get('x-hub-signature-256')
        if not signature:
            return False

        body = await request.body()
        expected = (
            'sha256='
            + hmac.new(
                self._webhook_secret.encode(),
                body,
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(signature, expected)

    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse GitHub webhook payload into an IntegrationEvent.

        Uses typed views models (H9) for type-safe payload access.
        """
        typed = GitHubWebhookPayload.model_validate(payload)
        action = typed.action or ''

        # Issue labeled event
        if typed.issue and action == 'labeled':
            label_name = (typed.label.name or '') if typed.label else ''
            if label_name.lower() not in ('openhands', 'apollosai'):
                return None
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='issue_labeled',
                external_id=str(typed.issue.number),
                external_url=typed.issue.html_url,
                title=typed.issue.title,
                body=typed.issue.body,
                repo_url=typed.repository.html_url if typed.repository else None,
                user_email=typed.sender.email if typed.sender else None,
                raw_payload=payload,
            )

        # Issue comment with @openhands mention
        if typed.comment and typed.issue and action == 'created':
            comment_body = typed.comment.body or ''
            if '@openhands' not in comment_body.lower():
                return None
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='issue_comment',
                external_id=str(typed.issue.number),
                external_url=typed.comment.html_url,
                title=typed.issue.title,
                body=comment_body,
                repo_url=typed.repository.html_url if typed.repository else None,
                user_email=typed.sender.email if typed.sender else None,
                raw_payload=payload,
            )

        # PR review comment
        if typed.pull_request and action in ('submitted', 'created'):
            comment = typed.comment or typed.review
            comment_body = comment.body if comment else ''
            if not comment_body or '@openhands' not in comment_body.lower():
                return None
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='pr_review_comment',
                external_id=str(typed.pull_request.number),
                external_url=comment.html_url if comment else None,
                title=typed.pull_request.title,
                body=comment_body,
                repo_url=typed.repository.html_url if typed.repository else None,
                user_email=typed.sender.email if typed.sender else None,
                raw_payload=payload,
            )

        return None

    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a GitHub event."""
        title = event.title or f'GitHub {event.event_type} #{event.external_id}'
        message = event.body or title
        return ConversationContext(
            title=title,
            initial_message=message,
            repo_url=event.repo_url,
            metadata={
                'source': 'github',
                'event_type': event.event_type,
                'external_id': event.external_id,
                'external_url': event.external_url,
            },
        )

    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response comment back to GitHub."""
        if not self._api_token:
            logger.warning('No API token configured — cannot post response')
            return
        from apollosai.integrations.github.service import GitHubService

        service = GitHubService(self._api_token)
        # conversation_id expected format: "owner/repo#number"
        if '#' in conversation_id:
            repo, number_str = conversation_id.rsplit('#', 1)
            await service.post_comment(repo, int(number_str), message)

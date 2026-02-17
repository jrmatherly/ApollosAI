"""GitHub integration manager for ApollosAI."""

import hashlib
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
        """Parse GitHub webhook payload into an IntegrationEvent."""
        action = payload.get('action', '')

        # Issue labeled event
        if 'issue' in payload and action == 'labeled':
            issue = payload['issue']
            label = payload.get('label', {}).get('name', '')
            if label.lower() not in ('openhands', 'apollosai'):
                return None
            repo = payload.get('repository', {})
            sender = payload.get('sender', {})
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='issue_labeled',
                external_id=str(issue['number']),
                external_url=issue.get('html_url'),
                title=issue.get('title'),
                body=issue.get('body'),
                repo_url=repo.get('html_url'),
                user_email=sender.get('email'),
                raw_payload=payload,
            )

        # Issue comment with @openhands mention
        if 'comment' in payload and 'issue' in payload and action == 'created':
            comment_body = payload['comment'].get('body', '')
            if '@openhands' not in comment_body.lower():
                return None
            issue = payload['issue']
            repo = payload.get('repository', {})
            sender = payload.get('sender', {})
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='issue_comment',
                external_id=str(issue['number']),
                external_url=payload['comment'].get('html_url'),
                title=issue.get('title'),
                body=comment_body,
                repo_url=repo.get('html_url'),
                user_email=sender.get('email'),
                raw_payload=payload,
            )

        # PR review comment
        if 'pull_request' in payload and action in ('submitted', 'created'):
            pr = payload['pull_request']
            repo = payload.get('repository', {})
            comment = payload.get('comment', payload.get('review', {}))
            comment_body = comment.get('body', '')
            if '@openhands' not in comment_body.lower():
                return None
            sender = payload.get('sender', {})
            return IntegrationEvent(
                source=IntegrationType.GITHUB,
                event_type='pr_review_comment',
                external_id=str(pr['number']),
                external_url=comment.get('html_url'),
                title=pr.get('title'),
                body=comment_body,
                repo_url=repo.get('html_url'),
                user_email=sender.get('email'),
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

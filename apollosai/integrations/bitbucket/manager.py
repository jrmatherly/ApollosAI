"""Bitbucket integration manager for ApollosAI."""

import hashlib
import hmac
import logging
import os

from fastapi import Request

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.bitbucket.views import BitbucketWebhookPayload
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)

logger = logging.getLogger(__name__)

TRIGGER_MENTION = '@openhands'


class BitbucketIntegrationManager(ApollosAIIntegrationManager):
    """Handles Bitbucket webhooks for PR and issue comments."""

    source_type = IntegrationType.BITBUCKET

    def __init__(
        self,
        webhook_secret: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
    ):
        super().__init__()
        self._webhook_secret = webhook_secret
        self._username = username
        self._app_password = app_password

    async def validate_webhook(self, request: Request) -> bool:
        """Validate Bitbucket webhook using HMAC-SHA256 signature.

        Bitbucket sends the signature in the X-Hub-Signature header.
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

        signature = request.headers.get('x-hub-signature')
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
        """Parse Bitbucket webhook payload into an IntegrationEvent.

        Uses typed views models (H9) for type-safe payload access.
        """
        typed = BitbucketWebhookPayload.model_validate(payload)

        # PR comment created
        if typed.pullrequest and typed.comment:
            content = typed.comment.content or {}
            body = content.get('raw', '')
            if TRIGGER_MENTION not in body.lower():
                return None

            repo_url = None
            if typed.repository and typed.repository.links:
                repo_url = typed.repository.links.get('html', {}).get('href')

            pr_links = typed.pullrequest.links or {}
            return IntegrationEvent(
                source=IntegrationType.BITBUCKET,
                event_type='pr_comment',
                external_id=str(typed.pullrequest.id),
                external_url=pr_links.get('html', {}).get('href'),
                title=typed.pullrequest.title,
                body=body,
                repo_url=repo_url,
                user_email=typed.actor.nickname if typed.actor else None,
                raw_payload=payload,
            )

        # Issue comment created
        if typed.issue and typed.comment:
            content = typed.comment.content or {}
            body = content.get('raw', '')
            if TRIGGER_MENTION not in body.lower():
                return None

            repo_url = None
            if typed.repository and typed.repository.links:
                repo_url = typed.repository.links.get('html', {}).get('href')

            issue_links = typed.issue.links or {}
            return IntegrationEvent(
                source=IntegrationType.BITBUCKET,
                event_type='issue_comment',
                external_id=str(typed.issue.id or ''),
                external_url=issue_links.get('html', {}).get('href'),
                title=typed.issue.title,
                body=body,
                repo_url=repo_url,
                user_email=typed.actor.nickname if typed.actor else None,
                raw_payload=payload,
            )

        return None

    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a Bitbucket event."""
        title = event.title or f'Bitbucket {event.event_type} #{event.external_id}'
        message = event.body or title
        return ConversationContext(
            title=title,
            initial_message=message,
            repo_url=event.repo_url,
            metadata={
                'source': 'bitbucket',
                'event_type': event.event_type,
                'external_id': event.external_id,
                'external_url': event.external_url,
            },
        )

    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response comment back to Bitbucket."""
        if not all([self._username, self._app_password]):
            logger.warning(
                'Bitbucket credentials not configured — cannot post response'
            )
            return
        from apollosai.integrations.bitbucket.service import BitbucketService

        service = BitbucketService(self._username, self._app_password)
        # conversation_id format: "workspace/repo:pr:123" or "workspace/repo:issue:456"
        if ':pr:' in conversation_id:
            parts = conversation_id.split(':pr:')
            ws_repo = parts[0]
            pr_id = int(parts[1])
            workspace, repo_slug = ws_repo.split('/', 1)
            await service.post_pr_comment(workspace, repo_slug, pr_id, message)
        elif ':issue:' in conversation_id:
            parts = conversation_id.split(':issue:')
            ws_repo = parts[0]
            issue_id = int(parts[1])
            workspace, repo_slug = ws_repo.split('/', 1)
            await service.post_issue_comment(workspace, repo_slug, issue_id, message)

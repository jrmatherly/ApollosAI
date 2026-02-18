"""Slack integration manager for ApollosAI."""

import hashlib
import hmac
import logging
import os
import time

from fastapi import Request
from starlette.responses import JSONResponse, Response

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
)
from apollosai.integrations.slack.views import SlackEventPayload

logger = logging.getLogger(__name__)

# Slack allows up to 5 minutes of clock skew for request signing
TIMESTAMP_MAX_AGE = 300


class SlackIntegrationManager(ApollosAIIntegrationManager):
    """Handles Slack Events API webhooks for app_mention and messages."""

    source_type = IntegrationType.SLACK

    def __init__(
        self,
        signing_secret: str | None = None,
        bot_token: str | None = None,
    ):
        super().__init__()
        self._signing_secret = signing_secret
        self._bot_token = bot_token

    async def validate_webhook(self, request: Request) -> bool:
        """Validate Slack request signing.

        Slack signs requests using HMAC-SHA256 with:
          v0:{timestamp}:{body}
        Compared against X-Slack-Signature header.
        Also rejects requests older than 5 minutes (replay protection).
        """
        if self._signing_secret is None:
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
                'No signing secret configured — rejecting request (fail-closed)'
            )
            return False

        timestamp = request.headers.get('x-slack-request-timestamp')
        signature = request.headers.get('x-slack-signature')
        if not timestamp or not signature:
            return False

        # Replay protection
        try:
            ts = int(timestamp)
        except ValueError:
            return False
        if abs(time.time() - ts) > TIMESTAMP_MAX_AGE:
            return False

        body = await request.body()
        basestring = f'v0:{timestamp}:{body.decode()}'.encode()
        expected = (
            'v0='
            + hmac.new(
                self._signing_secret.encode(),
                basestring,
                hashlib.sha256,
            ).hexdigest()
        )

        return hmac.compare_digest(signature, expected)

    async def handle_webhook(self, request: Request) -> dict | Response:
        """Override to handle Slack url_verification challenge.

        Validates signature first, then checks for url_verification.
        """
        # Validate signature before anything else
        if not await self.validate_webhook(request):
            return JSONResponse(status_code=401, content={'error': 'invalid_signature'})

        body = await request.body()
        content_type = request.headers.get('content-type', '')

        if 'application/json' in content_type:
            import json

            try:
                data = json.loads(body)
            except (json.JSONDecodeError, ValueError):
                return JSONResponse(
                    status_code=400, content={'error': 'invalid_payload'}
                )

            # Respond to url_verification after signature is verified
            if data.get('type') == 'url_verification':
                return {'challenge': data.get('challenge', '')}

        # For all other events, parse and process
        try:
            if 'application/json' in content_type:
                payload = json.loads(body)
            else:
                return JSONResponse(
                    status_code=400, content={'error': 'unsupported_content_type'}
                )
        except Exception:
            return JSONResponse(status_code=400, content={'error': 'invalid_payload'})

        event = await self.parse_event(payload)
        if event is None:
            return {'status': 'skipped'}

        # Replay protection (M1): reject duplicate external_ids
        if self._check_replay(event.external_id):
            logger.info(
                'replay_detected',
                extra={
                    'source': self.source_type.value,
                    'external_id': event.external_id,
                },
            )
            return {'status': 'duplicate'}

        context = await self.build_context(event)
        logger.info(
            'integration_event',
            extra={
                'source': self.source_type.value,
                'event_type': event.event_type,
                'external_id': event.external_id,
            },
        )
        return {'status': 'processed', 'title': context.title}

    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse Slack Events API payload into an IntegrationEvent.

        Uses typed views models (H9) for type-safe payload access.
        """
        typed = SlackEventPayload.model_validate(payload)

        if typed.type != 'event_callback':
            return None

        event = typed.event
        if not event:
            return None

        event_type = event.type

        # app_mention — bot was @mentioned
        if event_type == 'app_mention':
            return IntegrationEvent(
                source=IntegrationType.SLACK,
                event_type='app_mention',
                external_id=event.ts or '',
                title=f'Slack mention in #{event.channel or "unknown"}',
                body=event.text or '',
                user_email=None,  # Slack uses user IDs, not emails
                raw_payload=payload,
            )

        # Direct message to bot
        if event_type == 'message':
            if event.channel_type != 'im':
                return None
            # Ignore bot's own messages
            if event.bot_id:
                return None
            return IntegrationEvent(
                source=IntegrationType.SLACK,
                event_type='direct_message',
                external_id=event.ts or '',
                title='Slack DM',
                body=event.text or '',
                raw_payload=payload,
            )

        return None

    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a Slack event."""
        title = event.title or f'Slack {event.event_type}'
        message = event.body or title
        return ConversationContext(
            title=title,
            initial_message=message,
            metadata={
                'source': 'slack',
                'event_type': event.event_type,
                'external_id': event.external_id,
            },
        )

    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response message back to Slack."""
        if not self._bot_token:
            logger.warning('No bot token configured — cannot post response')
            return
        from apollosai.integrations.slack.service import SlackService

        service = SlackService(self._bot_token)
        # conversation_id format: "channel_id:thread_ts" or just "channel_id"
        if ':' in conversation_id:
            channel, thread_ts = conversation_id.split(':', 1)
            await service.post_message(channel, message, thread_ts=thread_ts)
        else:
            await service.post_message(conversation_id, message)

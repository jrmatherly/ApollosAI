"""Rich base manager for ApollosAI integrations."""

import logging
from abc import ABC, abstractmethod

from fastapi import Request
from starlette.responses import JSONResponse

from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    OAuthConfig,
    SourceType,
)

logger = logging.getLogger(__name__)


class ApollosAIIntegrationManager(ABC):
    """Base class for all integration managers.

    Provides shared infrastructure: webhook verification, event parsing,
    context building, and response posting.
    Subclasses implement platform-specific logic.
    """

    source_type: SourceType

    @abstractmethod
    async def validate_webhook(self, request: Request) -> bool:
        """Validate webhook signature. Return True if valid."""
        ...

    @abstractmethod
    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse raw webhook payload into a normalized IntegrationEvent.

        Return None to skip processing (irrelevant event).
        """
        ...

    @abstractmethod
    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a parsed event."""
        ...

    @abstractmethod
    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response message back to the integration platform."""
        ...

    def get_oauth_config(self) -> OAuthConfig | None:
        """Return OAuth config for integrations requiring OAuth. Default: None."""
        return None

    async def handle_webhook(self, request: Request) -> dict | JSONResponse:
        """Standard webhook processing pipeline.

        1. Validate signature (timing-safe HMAC comparison)
        2. Parse event
        3. Build context
        4. Log and return

        Override for custom flows (e.g., Slack url_verification challenge).
        """
        if not await self.validate_webhook(request):
            return JSONResponse(status_code=401, content={'error': 'invalid_signature'})

        content_type = request.headers.get('content-type', '')
        try:
            if 'application/json' in content_type:
                body = await request.json()
            elif 'application/x-www-form-urlencoded' in content_type:
                form = await request.form()
                body = dict(form)
            else:
                return JSONResponse(
                    status_code=400, content={'error': 'unsupported_content_type'}
                )
        except Exception:
            return JSONResponse(status_code=400, content={'error': 'invalid_payload'})

        event = await self.parse_event(body)
        if event is None:
            return {'status': 'skipped'}

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

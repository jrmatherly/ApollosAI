"""Microsoft 365 integration manager for ApollosAI.

Handles Graph API change notifications and provides MCP tool access
to Microsoft 365 services (documents, email).
"""

import hmac
import logging

from fastapi import Request
from starlette.responses import JSONResponse, PlainTextResponse

from apollosai.integrations.base import ApollosAIIntegrationManager
from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
    OAuthConfig,
)

logger = logging.getLogger(__name__)


class MicrosoftIntegrationManager(ApollosAIIntegrationManager):
    """Handles Microsoft Graph change notifications and MCP tools."""

    source_type = IntegrationType.MICROSOFT

    def __init__(
        self,
        client_state: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
    ):
        self._client_state = client_state
        self._tenant_id = tenant_id
        self._client_id = client_id

    async def validate_webhook(self, request: Request) -> bool:
        """Validate Graph change notification using client state.

        Microsoft Graph sends a clientState value in each notification
        that must match the one provided during subscription creation.
        """
        if self._client_state is None:
            logger.warning('No client state configured — skipping validation')
            return True

        body = await request.body()
        # For validation token requests, skip client_state check
        if b'validationToken' in body or request.query_params.get('validationToken'):
            return True

        try:
            import json

            data = json.loads(body)
            notifications = data.get('value', [])
            for notification in notifications:
                state = notification.get('clientState', '')
                if not hmac.compare_digest(state, self._client_state):
                    return False
            return True
        except Exception:
            return False

    async def handle_webhook(self, request: Request) -> dict | JSONResponse:
        """Override to handle Graph subscription validation.

        Microsoft Graph sends a validation request with a validationToken
        query parameter that must be echoed back as plain text.
        """
        validation_token = request.query_params.get('validationToken')
        if validation_token:
            return PlainTextResponse(
                content=validation_token,
                media_type='text/plain',
            )

        return await super().handle_webhook(request)

    async def parse_event(self, payload: dict) -> IntegrationEvent | None:
        """Parse Graph change notification into an IntegrationEvent."""
        notifications = payload.get('value', [])
        if not notifications:
            return None

        # Process the first notification (batch handling can be added later)
        notification = notifications[0]
        change_type = notification.get('changeType', '')
        resource = notification.get('resource', '')
        resource_data = notification.get('resourceData', {})

        if not resource:
            return None

        return IntegrationEvent(
            source=IntegrationType.MICROSOFT,
            event_type=f'graph_{change_type}',
            external_id=resource_data.get('id', resource),
            external_url=None,
            title=f'Graph {change_type}: {resource}',
            body=None,
            raw_payload=payload,
        )

    async def build_context(self, event: IntegrationEvent) -> ConversationContext:
        """Build conversation context from a Graph notification."""
        title = event.title or f'Microsoft {event.event_type}'
        return ConversationContext(
            title=title,
            initial_message=f'Microsoft 365 notification: {title}',
            metadata={
                'source': 'microsoft',
                'event_type': event.event_type,
                'external_id': event.external_id,
            },
        )

    async def post_response(self, conversation_id: str, message: str) -> None:
        """Post a response via Graph API (e.g., reply to a Teams message)."""
        logger.info(
            'Microsoft post_response not yet wired — conversation_id=%s',
            conversation_id,
        )

    def get_oauth_config(self) -> OAuthConfig | None:
        """Return OAuth config for Microsoft identity platform."""
        if not self._tenant_id or not self._client_id:
            return None
        return OAuthConfig(
            authorize_url=(
                f'https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/authorize'
            ),
            token_url=(
                f'https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/token'
            ),
            client_id=self._client_id,
            scopes=['https://graph.microsoft.com/.default'],
        )

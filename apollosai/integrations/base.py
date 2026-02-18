"""Rich base manager for ApollosAI integrations."""

import logging
import re
from abc import ABC, abstractmethod
from collections import OrderedDict

import httpx
from fastapi import Request
from starlette.responses import JSONResponse, Response

from apollosai.integrations.models import (
    ConversationContext,
    IntegrationEvent,
    IntegrationType,
    OAuthConfig,
)

logger = logging.getLogger(__name__)

# --- URL path validation (M3: SSRF prevention) ---

_REPO_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+$')
_JIRA_KEY_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]+-\d+$')
_SLUG_PATTERN = re.compile(r'^[a-zA-Z0-9._-]+$')


def validate_repo_path(repo: str) -> str:
    """Validate GitHub/Bitbucket repo path (owner/name)."""
    if not _REPO_PATTERN.match(repo):
        raise ValueError(f'Invalid repository path: {repo}')
    return repo


def validate_jira_key(key: str) -> str:
    """Validate Jira issue key (PROJECT-123)."""
    if not _JIRA_KEY_PATTERN.match(key):
        raise ValueError(f'Invalid Jira issue key: {key}')
    return key


def validate_slug(slug: str) -> str:
    """Validate URL slug component."""
    if not _SLUG_PATTERN.match(slug):
        raise ValueError(f'Invalid slug: {slug}')
    return slug


class IntegrationServiceMixin:
    """Provides a shared httpx.AsyncClient with connection pooling (H5)."""

    _client: httpx.AsyncClient | None = None

    async def get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def close(self) -> None:
        """Close the shared httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class ApollosAIIntegrationManager(ABC):
    """Base class for all integration managers.

    Provides shared infrastructure: webhook verification, event parsing,
    context building, and response posting.
    Subclasses implement platform-specific logic.
    """

    source_type: IntegrationType
    _seen_events: OrderedDict = OrderedDict()
    _MAX_SEEN: int = 10_000

    def _check_replay(self, external_id: str) -> bool:
        """Return True if this event was already processed (replay detected).

        Uses an OrderedDict as a bounded LRU cache. Oldest entries are
        evicted when the cache exceeds _MAX_SEEN entries.
        """
        if external_id in self._seen_events:
            return True
        self._seen_events[external_id] = True
        while len(self._seen_events) > self._MAX_SEEN:
            self._seen_events.popitem(last=False)
        return False

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

    async def handle_webhook(self, request: Request) -> dict | Response:
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

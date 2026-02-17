"""HTTP client for Slack Web API operations."""

import logging

import httpx

logger = logging.getLogger(__name__)


class SlackService:
    """Thin wrapper around Slack Web API using httpx."""

    BASE_URL = 'https://slack.com/api'

    def __init__(self, bot_token: str):
        self._bot_token = bot_token

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._bot_token}',
            'Content-Type': 'application/json; charset=utf-8',
        }

    async def post_message(
        self, channel: str, text: str, thread_ts: str | None = None
    ) -> dict:
        """Post a message to a Slack channel or thread."""
        payload: dict = {'channel': channel, 'text': text}
        if thread_ts:
            payload['thread_ts'] = thread_ts
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{self.BASE_URL}/chat.postMessage',
                json=payload,
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

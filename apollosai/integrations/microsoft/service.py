"""HTTP client for Microsoft Graph API operations."""

import logging

from apollosai.integrations.base import IntegrationServiceMixin

logger = logging.getLogger(__name__)


class GraphService(IntegrationServiceMixin):
    """Thin wrapper around Microsoft Graph API using httpx.

    Uses OAuth2 client credentials flow with MSAL token.

    TODO(phase4-H7): Evaluate migrating to msgraph-sdk for richer
    Graph API coverage (pagination, batch requests, delta queries).
    """

    BASE_URL = 'https://graph.microsoft.com/v1.0'

    def __init__(self, access_token: str):
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._token}',
            'Content-Type': 'application/json',
        }

    async def search_documents(self, query: str, site_id: str | None = None) -> dict:
        """Search documents via Graph Search API."""
        body = {
            'requests': [
                {
                    'entityTypes': ['driveItem'],
                    'query': {'queryString': query},
                }
            ]
        }
        if site_id:
            body['requests'][0]['sharePointSiteId'] = site_id
        client = await self.get_client()
        resp = await client.post(
            f'{self.BASE_URL}/search/query',
            json=body,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    async def get_drive_item(self, drive_id: str, item_id: str) -> dict:
        """Get a specific drive item."""
        url = f'{self.BASE_URL}/drives/{drive_id}/items/{item_id}'
        client = await self.get_client()
        resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def list_messages(self, user_id: str, top: int = 10) -> dict:
        """List recent email messages for a user."""
        url = f'{self.BASE_URL}/users/{user_id}/messages'
        client = await self.get_client()
        resp = await client.get(
            url,
            headers=self._headers(),
            params={'$top': top, '$orderby': 'receivedDateTime desc'},
        )
        resp.raise_for_status()
        return resp.json()

    async def send_message(self, user_id: str, message: dict) -> None:
        """Send an email message."""
        url = f'{self.BASE_URL}/users/{user_id}/sendMail'
        client = await self.get_client()
        resp = await client.post(
            url,
            json={'message': message},
            headers=self._headers(),
        )
        resp.raise_for_status()

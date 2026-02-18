"""HTTP client for Jira REST API operations."""

import logging

from apollosai.integrations.base import IntegrationServiceMixin, validate_jira_key

logger = logging.getLogger(__name__)


class JiraService(IntegrationServiceMixin):
    """Thin wrapper around Jira REST API v3."""

    def __init__(self, base_url: str, email: str, api_token: str):
        self._base_url = base_url.rstrip('/')
        self._email = email
        self._api_token = api_token

    async def post_comment(self, issue_key: str, body: str) -> dict:
        """Post a comment on a Jira issue using ADF format."""
        validate_jira_key(issue_key)
        url = f'{self._base_url}/rest/api/3/issue/{issue_key}/comment'
        adf_body = {
            'body': {
                'type': 'doc',
                'version': 1,
                'content': [
                    {
                        'type': 'paragraph',
                        'content': [{'type': 'text', 'text': body}],
                    }
                ],
            }
        }
        client = await self.get_client()
        resp = await client.post(
            url,
            json=adf_body,
            auth=(self._email, self._api_token),
            headers={'Accept': 'application/json'},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_issue(self, issue_key: str) -> dict:
        """Get issue details."""
        validate_jira_key(issue_key)
        url = f'{self._base_url}/rest/api/3/issue/{issue_key}'
        client = await self.get_client()
        resp = await client.get(
            url,
            auth=(self._email, self._api_token),
            headers={'Accept': 'application/json'},
        )
        resp.raise_for_status()
        return resp.json()

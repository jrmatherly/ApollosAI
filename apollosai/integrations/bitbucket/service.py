"""HTTP client for Bitbucket API v2 operations."""

import logging

from apollosai.integrations.base import IntegrationServiceMixin, validate_slug

logger = logging.getLogger(__name__)


class BitbucketService(IntegrationServiceMixin):
    """Thin wrapper around Bitbucket REST API v2."""

    BASE_URL = 'https://api.bitbucket.org/2.0'

    def __init__(self, username: str, app_password: str):
        self._username = username
        self._app_password = app_password

    async def post_pr_comment(
        self, workspace: str, repo_slug: str, pr_id: int, body: str
    ) -> dict:
        """Post a comment on a pull request."""
        validate_slug(workspace)
        validate_slug(repo_slug)
        url = (
            f'{self.BASE_URL}/repositories/{workspace}/{repo_slug}'
            f'/pullrequests/{pr_id}/comments'
        )
        client = await self.get_client()
        resp = await client.post(
            url,
            json={'content': {'raw': body}},
            auth=(self._username, self._app_password),
        )
        resp.raise_for_status()
        return resp.json()

    async def post_issue_comment(
        self, workspace: str, repo_slug: str, issue_id: int, body: str
    ) -> dict:
        """Post a comment on an issue."""
        validate_slug(workspace)
        validate_slug(repo_slug)
        url = (
            f'{self.BASE_URL}/repositories/{workspace}/{repo_slug}'
            f'/issues/{issue_id}/comments'
        )
        client = await self.get_client()
        resp = await client.post(
            url,
            json={'content': {'raw': body}},
            auth=(self._username, self._app_password),
        )
        resp.raise_for_status()
        return resp.json()

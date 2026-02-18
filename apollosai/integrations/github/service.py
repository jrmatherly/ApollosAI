"""HTTP client for GitHub API operations."""

import logging

from apollosai.integrations.base import IntegrationServiceMixin, validate_repo_path

logger = logging.getLogger(__name__)


class GitHubService(IntegrationServiceMixin):
    """Thin wrapper around GitHub REST API v3."""

    BASE_URL = 'https://api.github.com'

    def __init__(self, token: str):
        self._token = token

    def _headers(self) -> dict[str, str]:
        return {
            'Authorization': f'Bearer {self._token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }

    async def post_comment(self, repo: str, issue_number: int, body: str) -> dict:
        """Post a comment on an issue or PR."""
        validate_repo_path(repo)
        url = f'{self.BASE_URL}/repos/{repo}/issues/{issue_number}/comments'
        client = await self.get_client()
        resp = await client.post(url, json={'body': body}, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

    async def get_issue(self, repo: str, issue_number: int) -> dict:
        """Get issue details."""
        validate_repo_path(repo)
        url = f'{self.BASE_URL}/repos/{repo}/issues/{issue_number}'
        client = await self.get_client()
        resp = await client.get(url, headers=self._headers())
        resp.raise_for_status()
        return resp.json()

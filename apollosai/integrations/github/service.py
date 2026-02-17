"""HTTP client for GitHub API operations."""

import logging

import httpx

logger = logging.getLogger(__name__)


class GitHubService:
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
        url = f'{self.BASE_URL}/repos/{repo}/issues/{issue_number}/comments'
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json={'body': body}, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

    async def get_issue(self, repo: str, issue_number: int) -> dict:
        """Get issue details."""
        url = f'{self.BASE_URL}/repos/{repo}/issues/{issue_number}'
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            return resp.json()

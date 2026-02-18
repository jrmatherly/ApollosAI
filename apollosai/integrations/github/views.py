"""Pydantic models for GitHub webhook event contexts."""

from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str | None = None
    email: str | None = None


class GitHubRepo(BaseModel):
    full_name: str | None = None
    html_url: str | None = None
    clone_url: str | None = None


class GitHubIssue(BaseModel):
    number: int | None = None
    title: str | None = None
    body: str | None = None
    html_url: str | None = None
    user: GitHubUser | None = None


class GitHubComment(BaseModel):
    body: str | None = None
    html_url: str | None = None
    user: GitHubUser | None = None


class GitHubPullRequest(BaseModel):
    number: int | None = None
    title: str | None = None
    body: str | None = None
    html_url: str | None = None
    user: GitHubUser | None = None


class GitHubLabel(BaseModel):
    name: str | None = None


class GitHubWebhookPayload(BaseModel):
    """Top-level GitHub webhook payload for type-safe event parsing."""

    action: str | None = None
    issue: GitHubIssue | None = None
    comment: GitHubComment | None = None
    pull_request: GitHubPullRequest | None = None
    repository: GitHubRepo | None = None
    sender: GitHubUser | None = None
    label: GitHubLabel | None = None
    review: GitHubComment | None = None

"""Pydantic models for GitHub webhook event contexts."""

from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str
    email: str | None = None


class GitHubRepo(BaseModel):
    full_name: str
    html_url: str
    clone_url: str | None = None


class GitHubIssue(BaseModel):
    number: int
    title: str
    body: str | None = None
    html_url: str
    user: GitHubUser | None = None


class GitHubComment(BaseModel):
    body: str
    html_url: str
    user: GitHubUser | None = None


class GitHubPullRequest(BaseModel):
    number: int
    title: str
    body: str | None = None
    html_url: str
    user: GitHubUser | None = None

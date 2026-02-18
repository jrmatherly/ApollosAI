"""Pydantic models for Bitbucket webhook event contexts."""

from pydantic import BaseModel


class BitbucketUser(BaseModel):
    display_name: str | None = None
    uuid: str | None = None
    nickname: str | None = None


class BitbucketRepo(BaseModel):
    full_name: str | None = None
    uuid: str | None = None
    links: dict | None = None


class BitbucketPullRequest(BaseModel):
    id: int | None = None
    title: str | None = None
    description: str | None = None
    source: dict | None = None
    destination: dict | None = None
    links: dict | None = None


class BitbucketComment(BaseModel):
    id: int | None = None
    content: dict | None = None
    user: BitbucketUser | None = None


class BitbucketIssue(BaseModel):
    id: int | None = None
    title: str | None = None
    links: dict | None = None


class BitbucketWebhookPayload(BaseModel):
    """Top-level Bitbucket webhook payload for type-safe event parsing."""

    pullrequest: BitbucketPullRequest | None = None
    issue: BitbucketIssue | None = None
    comment: BitbucketComment | None = None
    repository: BitbucketRepo | None = None
    actor: BitbucketUser | None = None

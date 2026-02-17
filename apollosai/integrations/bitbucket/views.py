"""Pydantic models for Bitbucket webhook event contexts."""

from pydantic import BaseModel


class BitbucketUser(BaseModel):
    display_name: str | None = None
    uuid: str | None = None
    nickname: str | None = None


class BitbucketRepo(BaseModel):
    full_name: str
    uuid: str | None = None
    links: dict | None = None


class BitbucketPullRequest(BaseModel):
    id: int
    title: str
    description: str | None = None
    source: dict | None = None
    destination: dict | None = None


class BitbucketComment(BaseModel):
    id: int
    content: dict | None = None
    user: BitbucketUser | None = None

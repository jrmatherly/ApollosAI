"""Pydantic models for Jira webhook event contexts."""

from pydantic import BaseModel


class JiraUser(BaseModel):
    account_id: str | None = None
    email_address: str | None = None
    display_name: str | None = None


class JiraIssue(BaseModel):
    id: str
    key: str
    summary: str | None = None
    description: str | None = None
    self_url: str | None = None


class JiraComment(BaseModel):
    id: str
    body: str | None = None
    author: JiraUser | None = None

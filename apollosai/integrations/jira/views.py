"""Pydantic models for Jira webhook event contexts."""

from pydantic import BaseModel


class JiraUser(BaseModel):
    account_id: str | None = None
    email_address: str | None = None
    display_name: str | None = None


class JiraIssueFields(BaseModel):
    """Fields nested inside a Jira issue payload."""

    summary: str | None = None
    description: str | None = None
    labels: list = []


class JiraIssue(BaseModel):
    id: str | None = None
    key: str
    fields: JiraIssueFields = JiraIssueFields()
    self_url: str | None = None


class JiraComment(BaseModel):
    id: str | None = None
    body: str | dict | None = None
    author: JiraUser | None = None


class JiraChangelog(BaseModel):
    items: list[dict] = []


class JiraWebhookPayload(BaseModel):
    """Top-level Jira webhook payload for type-safe event parsing."""

    webhook_event: str | None = None
    issue: JiraIssue | None = None
    comment: JiraComment | None = None
    user: JiraUser | None = None
    changelog: JiraChangelog | None = None

    class Config:
        populate_by_name = True

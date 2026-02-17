"""Pydantic models for Slack webhook event contexts."""

from pydantic import BaseModel


class SlackEvent(BaseModel):
    type: str
    channel: str | None = None
    user: str | None = None
    text: str | None = None
    ts: str | None = None
    thread_ts: str | None = None


class SlackEventPayload(BaseModel):
    """Top-level Slack Events API payload."""

    type: str  # 'url_verification' or 'event_callback'
    token: str | None = None
    challenge: str | None = None
    event: SlackEvent | None = None
    team_id: str | None = None

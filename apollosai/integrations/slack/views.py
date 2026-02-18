"""Pydantic models for Slack webhook event contexts."""

from typing import Any

from pydantic import BaseModel


class SlackEvent(BaseModel):
    type: str | None = None
    channel: Any = None  # Can be string ID or dict depending on event type
    user: str | None = None
    text: str | None = None
    ts: str | None = None
    thread_ts: str | None = None
    channel_type: str | None = None
    bot_id: str | None = None


class SlackEventPayload(BaseModel):
    """Top-level Slack Events API payload."""

    type: str | None = None
    token: str | None = None
    challenge: str | None = None
    event: SlackEvent | None = None
    team_id: str | None = None

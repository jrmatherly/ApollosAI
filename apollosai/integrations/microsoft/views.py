"""Pydantic models for Microsoft Graph webhook event contexts."""

from pydantic import BaseModel


class GraphSubscriptionNotification(BaseModel):
    """A single change notification from Graph API."""

    subscription_id: str | None = None
    client_state: str | None = None
    change_type: str | None = None
    resource: str | None = None
    resource_data: dict | None = None


class GraphSubscriptionPayload(BaseModel):
    """Top-level Graph change notification payload."""

    value: list[GraphSubscriptionNotification] = []
    validation_tokens: list[str] | None = None

"""Pydantic models for Microsoft Graph webhook event contexts."""

from pydantic import BaseModel, ConfigDict, Field


class GraphSubscriptionNotification(BaseModel):
    """A single change notification from Graph API."""

    model_config = ConfigDict(populate_by_name=True)

    subscription_id: str | None = Field(default=None, alias='subscriptionId')
    client_state: str | None = Field(default=None, alias='clientState')
    change_type: str | None = Field(default=None, alias='changeType')
    resource: str | None = None
    resource_data: dict | None = Field(default=None, alias='resourceData')


class GraphSubscriptionPayload(BaseModel):
    """Top-level Graph change notification payload."""

    model_config = ConfigDict(populate_by_name=True)

    value: list[GraphSubscriptionNotification] = []
    validation_tokens: list[str] | None = Field(default=None, alias='validationTokens')

"""Shared models for the integration framework.

This module is the SINGLE SOURCE OF TRUTH for integration type enums.
Storage models import IntegrationType from here — do not redefine in storage models.
"""

import enum

from pydantic import BaseModel


class IntegrationType(str, enum.Enum):
    GITHUB = 'github'
    JIRA = 'jira'
    SLACK = 'slack'
    BITBUCKET = 'bitbucket'
    MICROSOFT = 'microsoft'
    OPENHANDS = 'openhands'  # internal events only


# Alias for backward compatibility in integration code
SourceType = IntegrationType


class IntegrationEvent(BaseModel):
    """Normalized event from any integration."""

    source: SourceType
    event_type: str
    external_id: str
    external_url: str | None = None
    title: str | None = None
    body: str | None = None
    repo_url: str | None = None
    user_email: str | None = None
    raw_payload: dict | None = None


class ConversationContext(BaseModel):
    """Context passed to conversation creation from an integration."""

    title: str
    initial_message: str
    repo_url: str | None = None
    metadata: dict | None = None


class OAuthConfig(BaseModel):
    """OAuth configuration for an integration."""

    authorize_url: str
    token_url: str
    client_id: str
    scopes: list[str]


__all__ = [
    'ConversationContext',
    'IntegrationEvent',
    'IntegrationType',
    'OAuthConfig',
    'SourceType',
]

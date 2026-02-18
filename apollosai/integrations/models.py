"""Shared models for the integration framework.

This module is the SINGLE SOURCE OF TRUTH for integration type enums.
Storage models import IntegrationType from here — do not redefine in storage models.
"""

import enum
from typing import Any

from pydantic import BaseModel, model_validator

# Keys whose values are redacted from webhook payloads before storage (M5)
_SENSITIVE_KEYS = frozenset(
    {
        'token',
        'secret',
        'password',
        'authorization',
        'api_key',
        'access_token',
        'refresh_token',
        'client_secret',
    }
)


def sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip potentially sensitive fields from webhook payload before storage.

    Recursively walks the payload dict and replaces values of sensitive keys
    with '[REDACTED]'. Lists of dicts are also recursively processed.
    """
    result: dict[str, Any] = {}
    for k, v in payload.items():
        if k.lower() in _SENSITIVE_KEYS:
            result[k] = '[REDACTED]'
        elif isinstance(v, dict):
            result[k] = sanitize_payload(v)
        elif isinstance(v, list):
            result[k] = [
                sanitize_payload(item) if isinstance(item, dict) else item for item in v
            ]
        else:
            result[k] = v
    return result


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

    @model_validator(mode='after')
    def _sanitize_raw_payload(self) -> 'IntegrationEvent':
        """Auto-sanitize raw_payload on construction (M5)."""
        if self.raw_payload is not None:
            self.raw_payload = sanitize_payload(self.raw_payload)
        return self


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
    'sanitize_payload',
]

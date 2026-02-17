"""Shared models for the integration framework.

This module is the SINGLE SOURCE OF TRUTH for integration type enums.
Storage models import IntegrationType from here — do not redefine in storage models.
NOTE: Created in Phase 3A Task 2 with enum only. Phase 3B Task 9 extends with
IntegrationEvent, ConversationContext, OAuthConfig Pydantic models.
"""

import enum


class IntegrationType(str, enum.Enum):
    GITHUB = 'github'
    JIRA = 'jira'
    SLACK = 'slack'
    BITBUCKET = 'bitbucket'
    MICROSOFT = 'microsoft'
    OPENHANDS = 'openhands'  # internal events only


# Alias for backward compatibility in integration code
SourceType = IntegrationType

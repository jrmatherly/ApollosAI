"""Pydantic request/response models for ApollosAI API routes.

Review fix [M1]: Input validation on org/team names to prevent XSS.
"""

import uuid

from pydantic import BaseModel, Field

# --- Organization ---


class CreateOrgRequest(BaseModel):
    """Request body for creating an organization."""

    name: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9\s\-_]+$')


class UpdateOrgRequest(BaseModel):
    """Request body for updating an organization."""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9\s\-_]+$'
    )


class OrgResponse(BaseModel):
    """Response for a single organization."""

    id: uuid.UUID
    name: str


class OrgDetailResponse(OrgResponse):
    """Detailed organization response with settings."""

    default_llm_model: str | None = None
    default_max_iterations: int | None = None


# --- Organization Members ---


class AddMemberRequest(BaseModel):
    """Request body for adding a member to an org."""

    user_id: uuid.UUID
    role: str = Field(default='member', pattern=r'^(owner|admin|manager|member)$')


class OrgMemberResponse(BaseModel):
    """Response for an org member."""

    user_id: uuid.UUID
    email: str | None = None
    role_name: str
    role_rank: int


# --- Team ---


class CreateTeamRequest(BaseModel):
    """Request body for creating a team."""

    name: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9\s\-_]+$')
    org_id: uuid.UUID


class UpdateTeamRequest(BaseModel):
    """Request body for updating a team."""

    name: str | None = Field(
        default=None, min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9\s\-_]+$'
    )


class TeamResponse(BaseModel):
    """Response for a single team."""

    id: uuid.UUID
    name: str
    org_id: uuid.UUID


class AddTeamMemberRequest(BaseModel):
    """Request body for adding a member to a team."""

    user_id: uuid.UUID
    role: str = Field(default='member', pattern=r'^(admin|manager|member)$')

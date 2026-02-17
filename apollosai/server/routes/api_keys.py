"""API key management routes: create, list, revoke.

POST /api/orgs/{org_id}/keys   — Create a new API key (returns plaintext once)
GET  /api/orgs/{org_id}/keys   — List user's active keys (prefix + name only)
DELETE /api/orgs/{org_id}/keys/{key_id} — Revoke an API key
"""

import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.storage.services.api_key_service import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter()
_require_member = require_role('member')


class CreateApiKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(min_length=1, max_length=100)


class ApiKeyResponse(BaseModel):
    """Response for a single API key (no secrets)."""

    id: uuid.UUID
    name: str
    prefix: str
    created_at: str | None = None


class CreateApiKeyResponse(BaseModel):
    """Response for newly created API key (includes plaintext key ONCE)."""

    key: str
    id: uuid.UUID
    name: str
    prefix: str


@router.post('/api/orgs/{org_id}/keys')
async def create_key(
    org_id: uuid.UUID,
    body: CreateApiKeyRequest,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new API key. Returns the plaintext key exactly once."""
    raw_key, record = await create_api_key(
        session,
        user_id=user.user_id,
        org_id=org_id,
        name=body.name,
    )
    return CreateApiKeyResponse(
        key=raw_key,
        id=record.id,
        name=record.name,
        prefix=record.prefix,
    )


@router.get('/api/orgs/{org_id}/keys')
async def list_keys(
    org_id: uuid.UUID,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """List active API keys for the authenticated user."""
    keys = await list_api_keys(session, user_id=user.user_id, org_id=org_id)
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            prefix=k.prefix,
            created_at=str(k.created_at)
            if hasattr(k, 'created_at') and k.created_at
            else None,
        )
        for k in keys
    ]


@router.delete('/api/orgs/{org_id}/keys/{key_id}')
async def delete_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Revoke an API key."""
    try:
        await revoke_api_key(session, key_id=key_id, user_id=user.user_id)
    except ValueError:
        return JSONResponse(status_code=404, content={'error': 'Key not found'})
    except PermissionError:
        return JSONResponse(
            status_code=403, content={'error': "Cannot revoke another user's key"}
        )
    return {'status': 'revoked'}

"""API key management routes: create, list, revoke.

POST /api/keys   — Create a new API key (returns plaintext once)
GET  /api/keys   — List user's active keys (prefix + name only)
DELETE /api/keys/{key_id} — Revoke an API key
"""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.server.deps import get_db_session
from apollosai.storage.services.api_key_service import (
    create_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter()


class CreateApiKeyRequest(BaseModel):
    """Request body for creating an API key."""

    name: str = Field(min_length=1, max_length=100)
    org_id: uuid.UUID


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


@router.post('/api/keys')
async def create_key(
    body: CreateApiKeyRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Create a new API key. Returns the plaintext key exactly once."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = await EntraIDUserAuth.get_instance(request)
    if not auth.user_id:
        return JSONResponse(status_code=401, content={'error': 'Not authenticated'})

    user_id = uuid.UUID(auth.user_id)
    raw_key, record = await create_api_key(
        session,
        user_id=user_id,
        org_id=body.org_id,
        name=body.name,
    )
    return CreateApiKeyResponse(
        key=raw_key,
        id=record.id,
        name=record.name,
        prefix=record.prefix,
    )


@router.get('/api/keys')
async def list_keys(
    org_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """List active API keys for the authenticated user."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = await EntraIDUserAuth.get_instance(request)
    if not auth.user_id:
        return JSONResponse(status_code=401, content={'error': 'Not authenticated'})

    user_id = uuid.UUID(auth.user_id)
    keys = await list_api_keys(session, user_id=user_id, org_id=org_id)
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


@router.delete('/api/keys/{key_id}')
async def delete_key(
    key_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Revoke an API key."""
    from apollosai.server.auth.entraid_auth import EntraIDUserAuth

    auth = await EntraIDUserAuth.get_instance(request)
    if not auth.user_id:
        return JSONResponse(status_code=401, content={'error': 'Not authenticated'})

    user_id = uuid.UUID(auth.user_id)
    try:
        await revoke_api_key(session, key_id=key_id, user_id=user_id)
    except ValueError:
        return JSONResponse(status_code=404, content={'error': 'Key not found'})
    except PermissionError:
        return JSONResponse(
            status_code=403, content={'error': "Cannot revoke another user's key"}
        )
    return {'status': 'revoked'}

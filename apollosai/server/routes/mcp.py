"""BYOMCP routes: CRUD for user-defined MCP servers."""

import json
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apollosai.mcp.config import ApollosAIMCPConfig
from apollosai.server.auth.rbac import require_role
from apollosai.server.deps import get_db_session
from apollosai.server.routes.models import (
    CreateMCPServerRequest,
    MCPServerResponse,
    UpdateMCPServerRequest,
)
from apollosai.storage.models.user_mcp_server import MCPServerType, UserMCPServer

router = APIRouter()
_require_member = require_role('member')


@router.get('/api/orgs/{org_id}/mcp/servers')
async def list_mcp_servers(
    org_id: uuid.UUID,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """List user's MCP servers for the org."""
    stmt = select(UserMCPServer).where(
        UserMCPServer.user_id == user.user_id,
        UserMCPServer.org_id == org_id,
    )
    result = await session.execute(stmt)
    servers = result.scalars().all()
    return [
        MCPServerResponse(
            id=srv.id,
            name=srv.name,
            server_type=srv.server_type,
            enabled=srv.enabled,
            approved=srv.approved,
            description=srv.description,
            created_at=srv.created_at,
        )
        for srv in servers
    ]


@router.post('/api/orgs/{org_id}/mcp/servers')
async def create_mcp_server(
    org_id: uuid.UUID,
    body: CreateMCPServerRequest,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Add a new MCP server for the user."""
    server = UserMCPServer(
        user_id=user.user_id,
        org_id=org_id,
        name=body.name,
        server_type=MCPServerType(body.server_type).value,
        # TODO(phase3c): encrypt via SecretsStore before persisting
        config_encrypted=json.dumps(body.config_json),
        enabled=True,
        approved=False,  # requires admin approval
        description=body.description,
    )
    session.add(server)
    await session.commit()
    await session.refresh(server)
    ApollosAIMCPConfig.invalidate_mcp_cache(str(user.user_id))
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        server_type=server.server_type,
        enabled=server.enabled,
        approved=server.approved,
        description=server.description,
        created_at=server.created_at,
    )


@router.put('/api/orgs/{org_id}/mcp/servers/{server_id}')
async def update_mcp_server(
    org_id: uuid.UUID,
    server_id: uuid.UUID,
    body: UpdateMCPServerRequest,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Update an existing MCP server."""
    stmt = select(UserMCPServer).where(
        UserMCPServer.id == server_id,
        UserMCPServer.user_id == user.user_id,
        UserMCPServer.org_id == org_id,
    )
    result = await session.execute(stmt)
    server = result.scalar_one_or_none()
    if server is None:
        return JSONResponse(status_code=404, content={'error': 'MCP server not found'})

    if body.name is not None:
        server.name = body.name
    if body.config_json is not None:
        # TODO(phase3c): encrypt via SecretsStore before persisting
        server.config_encrypted = json.dumps(body.config_json)
    if body.enabled is not None:
        server.enabled = body.enabled
    if body.description is not None:
        server.description = body.description

    await session.commit()
    await session.refresh(server)
    ApollosAIMCPConfig.invalidate_mcp_cache(str(user.user_id))
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        server_type=server.server_type,
        enabled=server.enabled,
        approved=server.approved,
        description=server.description,
        created_at=server.created_at,
    )


@router.delete('/api/orgs/{org_id}/mcp/servers/{server_id}')
async def delete_mcp_server(
    org_id: uuid.UUID,
    server_id: uuid.UUID,
    user=Depends(_require_member),
    session: AsyncSession = Depends(get_db_session),
):
    """Delete an MCP server."""
    stmt = select(UserMCPServer).where(
        UserMCPServer.id == server_id,
        UserMCPServer.user_id == user.user_id,
        UserMCPServer.org_id == org_id,
    )
    result = await session.execute(stmt)
    server = result.scalar_one_or_none()
    if server is None:
        return JSONResponse(status_code=404, content={'error': 'MCP server not found'})

    await session.delete(server)
    await session.commit()
    ApollosAIMCPConfig.invalidate_mcp_cache(str(user.user_id))
    return {'status': 'deleted'}

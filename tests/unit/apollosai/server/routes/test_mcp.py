"""Tests for BYOMCP CRUD routes."""

import uuid

import pytest
from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.testclient import TestClient

import apollosai.storage.models.organization  # noqa: F401
import apollosai.storage.models.role  # noqa: F401
import apollosai.storage.models.user  # noqa: F401
import apollosai.storage.models.user_mcp_server  # noqa: F401
from apollosai.server.auth.rbac import AuthedUser
from apollosai.server.routes.mcp import _require_member, router
from apollosai.storage.models.base import Base
from apollosai.storage.models.user_mcp_server import MCPServerType, UserMCPServer

ORG_ID = uuid.uuid4()
USER_ID = uuid.uuid4()

_fake_user = AuthedUser(
    user_id=USER_ID,
    email='test@example.com',
    org_id=ORG_ID,
    role_name='member',
    role_rank=3,
)


@pytest.fixture
async def _db_session():
    engine = create_async_engine('sqlite+aiosqlite://', echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = maker()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


def _make_app(session):
    app = FastAPI()

    async def _override_member(org_id: uuid.UUID):
        return _fake_user

    async def _override_session():
        yield session

    app.include_router(router)
    app.dependency_overrides[_require_member] = _override_member
    from apollosai.server.deps import get_db_session

    app.dependency_overrides[get_db_session] = _override_session
    return app


@pytest.mark.asyncio
async def test_create_mcp_server(_db_session):
    app = _make_app(_db_session)
    client = TestClient(app)
    resp = client.post(
        f'/api/orgs/{ORG_ID}/mcp/servers',
        json={
            'name': 'my-mcp',
            'server_type': 'stdio',
            'config_json': {'command': 'npx', 'args': ['-y', 'my-tool']},
            'description': 'Test MCP server',
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['name'] == 'my-mcp'
    assert data['server_type'] == 'stdio'
    assert data['enabled'] is True
    assert data['approved'] is False
    assert data['description'] == 'Test MCP server'


@pytest.mark.asyncio
async def test_list_mcp_servers(_db_session):
    # Seed a server
    srv = UserMCPServer(
        user_id=USER_ID,
        org_id=ORG_ID,
        name='existing',
        server_type=MCPServerType.STDIO,
        config_encrypted='{"command":"echo"}',
        enabled=True,
        approved=True,
    )
    _db_session.add(srv)
    await _db_session.commit()

    app = _make_app(_db_session)
    client = TestClient(app)
    resp = client.get(f'/api/orgs/{ORG_ID}/mcp/servers')
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]['name'] == 'existing'
    assert data[0]['approved'] is True


@pytest.mark.asyncio
async def test_update_mcp_server(_db_session):
    srv = UserMCPServer(
        user_id=USER_ID,
        org_id=ORG_ID,
        name='to-update',
        server_type=MCPServerType.SSE,
        config_encrypted='{}',
    )
    _db_session.add(srv)
    await _db_session.commit()
    await _db_session.refresh(srv)

    app = _make_app(_db_session)
    client = TestClient(app)
    resp = client.put(
        f'/api/orgs/{ORG_ID}/mcp/servers/{srv.id}',
        json={'name': 'updated-name', 'enabled': False},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data['name'] == 'updated-name'
    assert data['enabled'] is False


@pytest.mark.asyncio
async def test_update_mcp_server_not_found(_db_session):
    app = _make_app(_db_session)
    client = TestClient(app)
    fake_id = uuid.uuid4()
    resp = client.put(
        f'/api/orgs/{ORG_ID}/mcp/servers/{fake_id}',
        json={'name': 'nope'},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_mcp_server(_db_session):
    srv = UserMCPServer(
        user_id=USER_ID,
        org_id=ORG_ID,
        name='to-delete',
        server_type=MCPServerType.SHTTP,
        config_encrypted='{}',
    )
    _db_session.add(srv)
    await _db_session.commit()
    await _db_session.refresh(srv)

    app = _make_app(_db_session)
    client = TestClient(app)
    resp = client.delete(f'/api/orgs/{ORG_ID}/mcp/servers/{srv.id}')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'deleted'

    # Verify actually deleted
    result = await _db_session.execute(
        select(UserMCPServer).where(UserMCPServer.id == srv.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_mcp_server_not_found(_db_session):
    app = _make_app(_db_session)
    client = TestClient(app)
    fake_id = uuid.uuid4()
    resp = client.delete(f'/api/orgs/{ORG_ID}/mcp/servers/{fake_id}')
    assert resp.status_code == 404

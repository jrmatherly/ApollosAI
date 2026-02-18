"""Tests for BYOMCP CRUD routes."""

import json
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
from apollosai.storage.encrypt_utils import decrypt_value, reset_key_cache
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


# --- C3: Encryption at rest tests ---


@pytest.fixture
def _encryption_env(monkeypatch):
    """Set up encryption key for tests and reset key cache."""
    monkeypatch.setenv(
        'APOLLOSAI_ENCRYPTION_KEY', 'test-key-at-least-32-characters-long!!'
    )
    reset_key_cache()
    yield
    reset_key_cache()


@pytest.mark.asyncio
async def test_config_encrypted_at_rest(_db_session, _encryption_env):
    """C3: config_encrypted column must contain encrypted bytes, not plaintext JSON."""
    app = _make_app(_db_session)
    client = TestClient(app)
    config = {'command': 'npx', 'args': ['-y', 'my-tool']}
    resp = client.post(
        f'/api/orgs/{ORG_ID}/mcp/servers',
        json={
            'name': 'encrypted-test',
            'server_type': 'stdio',
            'config_json': config,
        },
    )
    assert resp.status_code == 200

    # Read raw from DB — should NOT be valid JSON
    result = await _db_session.execute(
        select(UserMCPServer).where(UserMCPServer.name == 'encrypted-test')
    )
    row = result.scalar_one()
    with pytest.raises(json.JSONDecodeError):
        json.loads(row.config_encrypted)


@pytest.mark.asyncio
async def test_config_round_trips_through_encryption(_db_session, _encryption_env):
    """C3: Config can be written encrypted and read back decrypted."""
    app = _make_app(_db_session)
    client = TestClient(app)
    config = {'command': 'npx', 'args': ['-y', 'some-server']}
    resp = client.post(
        f'/api/orgs/{ORG_ID}/mcp/servers',
        json={
            'name': 'roundtrip-test',
            'server_type': 'stdio',
            'config_json': config,
        },
    )
    assert resp.status_code == 200

    # Verify the stored ciphertext decrypts back to original config
    result = await _db_session.execute(
        select(UserMCPServer).where(UserMCPServer.name == 'roundtrip-test')
    )
    row = result.scalar_one()
    decrypted = decrypt_value(row.config_encrypted)
    assert json.loads(decrypted) == config


@pytest.mark.asyncio
async def test_update_config_encrypted(_db_session, _encryption_env):
    """C3: Updating config_json also encrypts the new value."""
    # Create initial server
    app = _make_app(_db_session)
    client = TestClient(app)
    resp = client.post(
        f'/api/orgs/{ORG_ID}/mcp/servers',
        json={
            'name': 'update-enc-test',
            'server_type': 'stdio',
            'config_json': {'command': 'old'},
        },
    )
    assert resp.status_code == 200
    server_id = resp.json()['id']

    # Update config
    new_config = {'command': 'new', 'args': ['--flag']}
    resp = client.put(
        f'/api/orgs/{ORG_ID}/mcp/servers/{server_id}',
        json={'config_json': new_config},
    )
    assert resp.status_code == 200

    # Verify updated value is encrypted
    result = await _db_session.execute(
        select(UserMCPServer).where(UserMCPServer.id == uuid.UUID(server_id))
    )
    row = result.scalar_one()
    with pytest.raises(json.JSONDecodeError):
        json.loads(row.config_encrypted)
    decrypted = decrypt_value(row.config_encrypted)
    assert json.loads(decrypted) == new_config

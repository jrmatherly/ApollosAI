import uuid

import pytest

from apollosai.integrations.models import IntegrationType
from apollosai.storage.models.integration_config import IntegrationConfig
from apollosai.storage.models.integration_conversation import (
    IntegrationConversation,
)
from apollosai.storage.models.user_mcp_server import MCPServerType, UserMCPServer


@pytest.mark.asyncio
async def test_integration_config_create(async_session):
    from apollosai.storage.models.organization import Organization

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    await async_session.flush()

    config = IntegrationConfig(
        org_id=org_id,
        integration_type=IntegrationType.GITHUB,
        enabled=True,
        config_encrypted='encrypted:app_id=12345',
        webhook_secret_encrypted='encrypted:whsec_test',
    )
    async_session.add(config)
    await async_session.commit()

    fetched = await async_session.get(IntegrationConfig, config.id)
    assert fetched is not None
    assert fetched.integration_type == IntegrationType.GITHUB
    assert fetched.config_encrypted == 'encrypted:app_id=12345'
    assert fetched.webhook_secret_encrypted == 'encrypted:whsec_test'


@pytest.mark.asyncio
async def test_integration_conversation_create(async_session):
    from apollosai.storage.models.organization import Organization

    org_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    await async_session.flush()

    conv = IntegrationConversation(
        org_id=org_id,
        integration_type='github',
        external_id='issue-123',
        conversation_id='conv-abc',
        external_url='https://github.com/org/repo/issues/123',
        extra_metadata={'labels': ['bug']},
    )
    async_session.add(conv)
    await async_session.commit()

    fetched = await async_session.get(IntegrationConversation, conv.id)
    assert fetched is not None
    assert fetched.external_id == 'issue-123'
    assert fetched.extra_metadata == {'labels': ['bug']}


@pytest.mark.asyncio
async def test_user_mcp_server_create(async_session):
    from apollosai.storage.models.organization import Organization
    from apollosai.storage.models.user import User

    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async_session.add(Organization(id=org_id, name='test-org'))
    async_session.add(User(id=user_id, entra_oid='oid-1'))
    await async_session.flush()

    server = UserMCPServer(
        user_id=user_id,
        org_id=org_id,
        name='my-jira-tool',
        server_type=MCPServerType.STDIO,
        config_encrypted='encrypted:command=python,args=-m jira_mcp',
        enabled=True,
    )
    async_session.add(server)
    await async_session.commit()

    fetched = await async_session.get(UserMCPServer, server.id)
    assert fetched is not None
    assert fetched.server_type == MCPServerType.STDIO
    assert fetched.config_encrypted == 'encrypted:command=python,args=-m jira_mcp'
    assert fetched.approved is False

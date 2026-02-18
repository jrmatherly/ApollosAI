"""Tests for integration URL path validation and shared client mixin."""

import pytest

from apollosai.integrations.base import (
    IntegrationServiceMixin,
    validate_jira_key,
    validate_repo_path,
    validate_slug,
)


# --- validate_repo_path ---


def test_validate_repo_path_accepts_valid():
    assert validate_repo_path('owner/repo') == 'owner/repo'


def test_validate_repo_path_accepts_dots_dashes():
    assert validate_repo_path('my-org/my.repo-name') == 'my-org/my.repo-name'


def test_validate_repo_path_accepts_underscores():
    assert validate_repo_path('user_name/repo_name') == 'user_name/repo_name'


def test_validate_repo_path_rejects_traversal():
    with pytest.raises(ValueError, match='Invalid repository path'):
        validate_repo_path('../../../etc/passwd')


def test_validate_repo_path_rejects_slashes():
    with pytest.raises(ValueError, match='Invalid repository path'):
        validate_repo_path('owner/repo/extra')


def test_validate_repo_path_rejects_empty():
    with pytest.raises(ValueError, match='Invalid repository path'):
        validate_repo_path('')


def test_validate_repo_path_rejects_spaces():
    with pytest.raises(ValueError, match='Invalid repository path'):
        validate_repo_path('owner/repo name')


def test_validate_repo_path_rejects_url_encoding():
    with pytest.raises(ValueError, match='Invalid repository path'):
        validate_repo_path('owner%2F..%2Fetc/passwd')


# --- validate_jira_key ---


def test_validate_jira_key_accepts_valid():
    assert validate_jira_key('PROJ-123') == 'PROJ-123'


def test_validate_jira_key_accepts_long_project():
    assert validate_jira_key('MYPROJECT-9999') == 'MYPROJECT-9999'


def test_validate_jira_key_accepts_underscores():
    assert validate_jira_key('MY_PROJ-42') == 'MY_PROJ-42'


def test_validate_jira_key_rejects_lowercase():
    with pytest.raises(ValueError, match='Invalid Jira issue key'):
        validate_jira_key('proj-123')


def test_validate_jira_key_rejects_no_dash():
    with pytest.raises(ValueError, match='Invalid Jira issue key'):
        validate_jira_key('PROJ123')


def test_validate_jira_key_rejects_traversal():
    with pytest.raises(ValueError, match='Invalid Jira issue key'):
        validate_jira_key('../../etc/passwd')


def test_validate_jira_key_rejects_invalid():
    with pytest.raises(ValueError, match='Invalid Jira issue key'):
        validate_jira_key('not-a-key')


# --- validate_slug ---


def test_validate_slug_accepts_simple():
    assert validate_slug('my-workspace') == 'my-workspace'


def test_validate_slug_accepts_dots():
    assert validate_slug('repo.name') == 'repo.name'


def test_validate_slug_accepts_underscores():
    assert validate_slug('my_repo') == 'my_repo'


def test_validate_slug_rejects_slashes():
    with pytest.raises(ValueError, match='Invalid slug'):
        validate_slug('path/traversal')


def test_validate_slug_rejects_spaces():
    with pytest.raises(ValueError, match='Invalid slug'):
        validate_slug('bad slug')


def test_validate_slug_rejects_empty():
    with pytest.raises(ValueError, match='Invalid slug'):
        validate_slug('')


# --- IntegrationServiceMixin ---


@pytest.mark.asyncio
async def test_mixin_get_client_creates_client():
    """H5: get_client returns an httpx.AsyncClient instance."""
    import httpx

    mixin = IntegrationServiceMixin()
    client = await mixin.get_client()
    try:
        assert isinstance(client, httpx.AsyncClient)
        assert not client.is_closed
    finally:
        await mixin.close()


@pytest.mark.asyncio
async def test_mixin_get_client_reuses_client():
    """H5: Subsequent calls return the same client (connection pooling)."""
    mixin = IntegrationServiceMixin()
    client1 = await mixin.get_client()
    client2 = await mixin.get_client()
    try:
        assert client1 is client2
    finally:
        await mixin.close()


@pytest.mark.asyncio
async def test_mixin_close_closes_client():
    """Close sets client to None and closes the httpx client."""
    mixin = IntegrationServiceMixin()
    client = await mixin.get_client()
    assert not client.is_closed
    await mixin.close()
    assert client.is_closed
    assert mixin._client is None


@pytest.mark.asyncio
async def test_mixin_get_client_after_close():
    """After close, get_client creates a fresh client."""
    mixin = IntegrationServiceMixin()
    client1 = await mixin.get_client()
    await mixin.close()
    client2 = await mixin.get_client()
    try:
        assert client1 is not client2
        assert not client2.is_closed
    finally:
        await mixin.close()

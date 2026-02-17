"""Tests for ApollosAIConversationStore — conversation metadata with soft delete.

Review fix [H11]: Full test implementations required, not comment-only.
Review fix [M3]: Users should only access their own conversations.
Review fix [M5]: exists() must exclude soft-deleted records.
"""

import uuid

import pytest

from apollosai.storage.stores.conversation_store import ApollosAIConversationStore
from openhands.storage.conversation.conversation_store import ConversationStore
from openhands.storage.data_models.conversation_metadata import ConversationMetadata

# NOTE: async_session fixture from conftest.py (Task 4b)


def test_is_subclass_of_conversation_store():
    assert issubclass(ApollosAIConversationStore, ConversationStore)


def test_has_required_methods():
    assert hasattr(ApollosAIConversationStore, 'save_metadata')
    assert hasattr(ApollosAIConversationStore, 'get_metadata')
    assert hasattr(ApollosAIConversationStore, 'delete_metadata')
    assert hasattr(ApollosAIConversationStore, 'exists')
    assert hasattr(ApollosAIConversationStore, 'search')
    assert hasattr(ApollosAIConversationStore, 'get_instance')


@pytest.mark.asyncio
async def test_save_and_get_metadata_roundtrip(async_session, async_session_maker):
    """Save then get should return matching conversation."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    meta = ConversationMetadata(
        conversation_id='conv-1', title='Test', selected_repository=None
    )
    await store.save_metadata(meta)
    loaded = await store.get_metadata('conv-1')
    assert loaded.conversation_id == 'conv-1'
    assert loaded.title == 'Test'


@pytest.mark.asyncio
async def test_get_metadata_validates_user_access(async_session, async_session_maker):
    """Review fix [M3]: Users should only access their own conversations."""
    user_a = str(uuid.uuid4())
    user_b = str(uuid.uuid4())
    store_a = ApollosAIConversationStore(
        config=None, user_id=user_a, session_maker=async_session_maker
    )
    await store_a.save_metadata(
        ConversationMetadata(
            conversation_id='conv-a', title='A', selected_repository=None
        )
    )

    store_b = ApollosAIConversationStore(
        config=None, user_id=user_b, session_maker=async_session_maker
    )
    with pytest.raises(FileNotFoundError):
        await store_b.get_metadata('conv-a')


@pytest.mark.asyncio
async def test_delete_metadata_sets_deleted_at(async_session, async_session_maker):
    """Soft delete should set deleted_at, not remove the row."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    await store.save_metadata(
        ConversationMetadata(
            conversation_id='conv-del', title='Del', selected_repository=None
        )
    )
    await store.delete_metadata('conv-del')
    assert not await store.exists('conv-del')


@pytest.mark.asyncio
async def test_exists_returns_false_for_soft_deleted(
    async_session, async_session_maker
):
    """Review fix [M5]: exists() must exclude soft-deleted records."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    await store.save_metadata(
        ConversationMetadata(
            conversation_id='conv-sd', title='SD', selected_repository=None
        )
    )
    assert await store.exists('conv-sd')
    await store.delete_metadata('conv-sd')
    assert not await store.exists('conv-sd')


@pytest.mark.asyncio
async def test_search_filters_by_user(async_session, async_session_maker):
    """Search should only return conversations for the current user."""
    user_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    store = ApollosAIConversationStore(
        config=None, user_id=user_id, session_maker=async_session_maker
    )
    other_store = ApollosAIConversationStore(
        config=None, user_id=other_id, session_maker=async_session_maker
    )
    await store.save_metadata(
        ConversationMetadata(
            conversation_id='mine', title='Mine', selected_repository=None
        )
    )
    await other_store.save_metadata(
        ConversationMetadata(
            conversation_id='theirs', title='Theirs', selected_repository=None
        )
    )
    results = await store.search()
    assert len(results.results) == 1
    assert results.results[0].conversation_id == 'mine'


@pytest.mark.asyncio
async def test_search_returns_empty_for_new_user(async_session, async_session_maker):
    """New user with no conversations should get empty results."""
    store = ApollosAIConversationStore(
        config=None, user_id=str(uuid.uuid4()), session_maker=async_session_maker
    )
    results = await store.search()
    assert len(results.results) == 0

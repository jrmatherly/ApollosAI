from apollosai.storage.stores.conversation_store import ApollosAIConversationStore
from openhands.storage.conversation.conversation_store import ConversationStore


def test_is_subclass_of_conversation_store():
    assert issubclass(ApollosAIConversationStore, ConversationStore)


def test_has_required_methods():
    assert hasattr(ApollosAIConversationStore, 'save_metadata')
    assert hasattr(ApollosAIConversationStore, 'get_metadata')
    assert hasattr(ApollosAIConversationStore, 'delete_metadata')
    assert hasattr(ApollosAIConversationStore, 'exists')
    assert hasattr(ApollosAIConversationStore, 'search')
    assert hasattr(ApollosAIConversationStore, 'get_instance')

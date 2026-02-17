from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.conversation.conversation_store import ConversationStore
from openhands.storage.data_models.conversation_metadata import ConversationMetadata
from openhands.storage.data_models.conversation_metadata_result_set import (
    ConversationMetadataResultSet,
)


class ApollosAIConversationStore(ConversationStore):
    """PostgreSQL-backed conversation store scoped to user + org."""

    def __init__(self, config: OpenHandsConfig, user_id: str | None):
        self.config = config
        self.user_id = user_id

    async def save_metadata(self, metadata: ConversationMetadata) -> None:
        # TODO: Persist to DB with user_id + org_id ownership
        pass

    async def get_metadata(self, conversation_id: str) -> ConversationMetadata:
        # TODO: Load from DB, validate user has access
        raise FileNotFoundError(f'Conversation {conversation_id} not found')

    async def delete_metadata(self, conversation_id: str) -> None:
        # TODO: Soft delete from DB
        pass

    async def exists(self, conversation_id: str) -> bool:
        # TODO: Check DB
        return False

    async def search(
        self,
        page_id: str | None = None,
        limit: int = 20,
    ) -> ConversationMetadataResultSet:
        # TODO: Query DB filtered by user_id + org_id
        return ConversationMetadataResultSet(results=[], next_page_id=None)

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAIConversationStore':
        return cls(config=config, user_id=user_id)

"""PostgreSQL-backed conversation store scoped to user + org.

Review fixes incorporated:
- [C1]: Uses get_session_maker() from lifespan module as V0 bridge
- [H11]: Full method implementations, not stubs
- [M3]: get_metadata validates user access (prevents IDOR)
- [M5]: exists() excludes soft-deleted records
"""

import datetime
import uuid as uuid_mod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.conversation.conversation_store import ConversationStore
from openhands.storage.data_models.conversation_metadata import ConversationMetadata
from openhands.storage.data_models.conversation_metadata_result_set import (
    ConversationMetadataResultSet,
)


class ApollosAIConversationStore(ConversationStore):
    """PostgreSQL-backed conversation store scoped to user + org."""

    def __init__(
        self,
        config: OpenHandsConfig | None,
        user_id: str | None,
        session_maker: async_sessionmaker | None = None,
    ):
        self.config = config
        self.user_id = user_id
        self.session_maker = session_maker

    async def save_metadata(self, metadata: ConversationMetadata) -> None:
        """Persist conversation metadata to DB."""
        if self.session_maker is None or self.user_id is None:
            return

        from apollosai.storage.models.conversation import Conversation

        async with self.session_maker() as session:
            # Check for existing record (upsert)
            existing = await session.get(Conversation, metadata.conversation_id)
            if existing is not None:
                existing.title = metadata.title
                existing.metadata_json = {
                    'selected_repository': metadata.selected_repository,
                    'selected_branch': metadata.selected_branch,
                    'llm_model': metadata.llm_model,
                }
            else:
                conv = Conversation(
                    id=metadata.conversation_id,
                    user_id=uuid_mod.UUID(self.user_id),
                    org_id=uuid_mod.UUID(
                        self.user_id
                    ),  # Placeholder: uses user_id as org_id
                    title=metadata.title,
                    metadata_json={
                        'selected_repository': metadata.selected_repository,
                        'selected_branch': metadata.selected_branch,
                        'llm_model': metadata.llm_model,
                    },
                )
                session.add(conv)
            await session.commit()

    async def get_metadata(self, conversation_id: str) -> ConversationMetadata:
        """Load conversation metadata, validating user access.

        Review fix [M3]: Use self.user_id from authenticated session to
        prevent IDOR (Insecure Direct Object Reference).
        """
        if self.session_maker is None or self.user_id is None:
            raise FileNotFoundError(f'Conversation {conversation_id} not found')

        from apollosai.storage.models.conversation import Conversation

        user_uuid = uuid_mod.UUID(self.user_id)

        async with self.session_maker() as session:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_uuid,
                Conversation.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv is None:
                raise FileNotFoundError(f'Conversation {conversation_id} not found')

            meta_json = conv.metadata_json or {}
            return ConversationMetadata(
                conversation_id=conv.id,
                title=conv.title,
                user_id=str(conv.user_id),
                selected_repository=meta_json.get('selected_repository'),
                selected_branch=meta_json.get('selected_branch'),
                llm_model=meta_json.get('llm_model'),
                created_at=conv.created_at,
                last_updated_at=conv.updated_at,
            )

    async def delete_metadata(self, conversation_id: str) -> None:
        """Soft delete — sets deleted_at rather than removing the row."""
        if self.session_maker is None or self.user_id is None:
            return

        from apollosai.storage.models.conversation import Conversation

        user_uuid = uuid_mod.UUID(self.user_id)

        async with self.session_maker() as session:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_uuid,
                Conversation.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv is not None:
                conv.deleted_at = datetime.datetime.now(datetime.timezone.utc)
                await session.commit()

    async def exists(self, conversation_id: str) -> bool:
        """Check if conversation exists (excluding soft-deleted).

        Review fix [M5]: Must exclude soft-deleted records.
        """
        if self.session_maker is None or self.user_id is None:
            return False

        from apollosai.storage.models.conversation import Conversation

        user_uuid = uuid_mod.UUID(self.user_id)

        async with self.session_maker() as session:
            stmt = select(Conversation.id).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_uuid,
                Conversation.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def search(
        self,
        page_id: str | None = None,
        limit: int = 20,
    ) -> ConversationMetadataResultSet:
        """Search conversations filtered by user, with cursor-based pagination."""
        if self.session_maker is None or self.user_id is None:
            return ConversationMetadataResultSet(results=[], next_page_id=None)

        from apollosai.storage.models.conversation import Conversation

        user_uuid = uuid_mod.UUID(self.user_id)

        async with self.session_maker() as session:
            stmt = (
                select(Conversation)
                .where(
                    Conversation.user_id == user_uuid,
                    Conversation.deleted_at.is_(None),
                )
                .order_by(Conversation.created_at.desc())
                .limit(limit + 1)  # Fetch one extra to detect next page
            )
            if page_id:
                # Cursor-based: fetch records older than the cursor
                stmt = stmt.where(Conversation.id < page_id)

            result = await session.execute(stmt)
            rows = result.scalars().all()

            has_next = len(rows) > limit
            if has_next:
                rows = rows[:limit]

            results = []
            for conv in rows:
                meta_json = conv.metadata_json or {}
                results.append(
                    ConversationMetadata(
                        conversation_id=conv.id,
                        title=conv.title,
                        user_id=str(conv.user_id),
                        selected_repository=meta_json.get('selected_repository'),
                        selected_branch=meta_json.get('selected_branch'),
                        llm_model=meta_json.get('llm_model'),
                        created_at=conv.created_at,
                        last_updated_at=conv.updated_at,
                    )
                )

            next_page = rows[-1].id if has_next else None
            return ConversationMetadataResultSet(
                results=results, next_page_id=next_page
            )

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAIConversationStore':
        """Review fix [C1]: Bridge V0 ABC by getting session_maker from lifespan module."""
        from apollosai.server.lifespan import get_session_maker

        return cls(config=config, user_id=user_id, session_maker=get_session_maker())

"""PostgreSQL-backed encrypted secrets per user/org.

Review fixes incorporated:
- [C1]: Uses get_session_maker() from lifespan module as V0 bridge
- [C9]: Full encrypted storage with AES-256-GCM
- [M14]: AAD-based tenant isolation (user_id:org_id)
"""

import json
import uuid as uuid_mod

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.secrets import Secrets
from openhands.storage.secrets.secrets_store import SecretsStore

_SECRETS_KEY = '__secrets__'


class ApollosAISecretsStore(SecretsStore):
    """PostgreSQL-backed encrypted secrets per user/org."""

    def __init__(
        self,
        config: OpenHandsConfig | None,
        user_id: str | None,
        session_maker: async_sessionmaker | None = None,
    ):
        self.config = config
        self.user_id = user_id
        self.session_maker = session_maker

    async def _resolve_org_id(self, session) -> uuid_mod.UUID | None:
        """Look up user's current org for AAD scoping."""
        from apollosai.storage.models.user import User

        if not self.user_id:
            return None
        user = await session.get(User, uuid_mod.UUID(self.user_id))
        if user is None:
            return None
        return user.current_org_id

    async def load(self) -> Secrets | None:
        """Load and decrypt secrets from DB."""
        if self.session_maker is None or self.user_id is None:
            return Secrets()

        from apollosai.storage.encrypt_utils import decrypt_value
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        user_uuid = uuid_mod.UUID(self.user_id)

        async with self.session_maker() as session:
            org_id = await self._resolve_org_id(session)
            if org_id is None:
                return Secrets()

            stmt = select(EncryptedSecret).where(
                EncryptedSecret.user_id == user_uuid,
                EncryptedSecret.org_id == org_id,
                EncryptedSecret.key == _SECRETS_KEY,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()
            if record is None:
                return Secrets()

            aad = f'{self.user_id}:{org_id}'
            decrypted_json = decrypt_value(record.encrypted_value, aad=aad)
            secrets_dict = json.loads(decrypted_json)
            return Secrets(**secrets_dict)

    async def store(self, secrets: Secrets) -> None:
        """Encrypt and persist secrets to DB."""
        if self.session_maker is None or self.user_id is None:
            return

        from apollosai.storage.encrypt_utils import encrypt_value
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        user_uuid = uuid_mod.UUID(self.user_id)
        secrets_dict = secrets.model_dump(context={'expose_secrets': True})
        json_str = json.dumps(secrets_dict)

        async with self.session_maker() as session:
            org_id = await self._resolve_org_id(session)
            if org_id is None:
                return

            aad = f'{self.user_id}:{org_id}'
            encrypted = encrypt_value(json_str, aad=aad)

            # Upsert: check for existing record
            stmt = select(EncryptedSecret).where(
                EncryptedSecret.user_id == user_uuid,
                EncryptedSecret.org_id == org_id,
                EncryptedSecret.key == _SECRETS_KEY,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if record is not None:
                record.encrypted_value = encrypted
            else:
                record = EncryptedSecret(
                    id=uuid_mod.uuid4(),
                    user_id=user_uuid,
                    org_id=org_id,
                    key=_SECRETS_KEY,
                    encrypted_value=encrypted,
                )
                session.add(record)

            await session.commit()

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> 'ApollosAISecretsStore':
        """Review fix [C1]: Bridge V0 ABC by getting session_maker from lifespan module."""
        from apollosai.server.lifespan import get_session_maker

        return cls(config=config, user_id=user_id, session_maker=get_session_maker())

"""Tests for Phase 2 models."""


class TestEncryptedSecret:
    """Test encrypted_secret model."""

    def test_tablename(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        assert EncryptedSecret.__tablename__ == 'encrypted_secret'

    def test_required_columns(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        columns = {c.name for c in EncryptedSecret.__table__.columns}
        assert {'id', 'user_id', 'org_id', 'key', 'encrypted_value'}.issubset(columns)

    def test_has_timestamps(self):
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        columns = {c.name for c in EncryptedSecret.__table__.columns}
        assert 'created_at' in columns
        assert 'updated_at' in columns

    def test_user_id_not_nullable(self):
        """Review fix [M13]: Critical columns must not be nullable."""
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        col = EncryptedSecret.__table__.columns['user_id']
        assert not col.nullable

    def test_has_unique_constraint(self):
        """Review fix [M13]: (user_id, org_id, key) must be unique."""
        from apollosai.storage.models.encrypted_secret import EncryptedSecret

        constraints = EncryptedSecret.__table__.constraints
        unique_constraints = [
            c for c in constraints if hasattr(c, 'columns') and len(c.columns) > 1
        ]
        assert len(unique_constraints) > 0


class TestConversation:
    """Test conversation model."""

    def test_tablename(self):
        from apollosai.storage.models.conversation import Conversation

        assert Conversation.__tablename__ == 'conversation'

    def test_required_columns(self):
        from apollosai.storage.models.conversation import Conversation

        columns = {c.name for c in Conversation.__table__.columns}
        assert {'id', 'user_id', 'org_id', 'title', 'created_at'}.issubset(columns)

    def test_has_soft_delete(self):
        from apollosai.storage.models.conversation import Conversation

        columns = {c.name for c in Conversation.__table__.columns}
        assert 'deleted_at' in columns


class TestServerSession:
    """Test server_session model."""

    def test_tablename(self):
        from apollosai.storage.models.server_session import ServerSession

        assert ServerSession.__tablename__ == 'server_session'

    def test_has_expires_at_index(self):
        """Review fix [L3]: Index on expires_at for efficient cleanup."""
        from apollosai.storage.models.server_session import ServerSession

        assert any(
            'expires_at' in str(idx.columns) for idx in ServerSession.__table__.indexes
        )


class TestRevokedToken:
    """Test revoked_token model."""

    def test_tablename(self):
        from apollosai.storage.models.revoked_token import RevokedToken

        assert RevokedToken.__tablename__ == 'revoked_token'

    def test_has_jti(self):
        from apollosai.storage.models.revoked_token import RevokedToken

        columns = {c.name for c in RevokedToken.__table__.columns}
        assert 'jti' in columns

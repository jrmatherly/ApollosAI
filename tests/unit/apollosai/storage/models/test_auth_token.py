from apollosai.storage.models.auth_token import AuthToken


def test_auth_token_tablename():
    assert AuthToken.__tablename__ == 'auth_token'


def test_auth_token_has_required_columns():
    col_names = {c.name for c in AuthToken.__table__.columns}
    assert {
        'id',
        'user_id',
        'token_cache',
        'created_at',
        'updated_at',
    }.issubset(col_names)


def test_auth_token_user_id_unique():
    user_id_col = AuthToken.__table__.columns['user_id']
    assert user_id_col.unique is True


def test_auth_token_id_defaults_to_uuid4():
    id_col = AuthToken.__table__.columns['id']
    assert id_col.default is not None

from apollosai.storage.models.api_key import ApiKey


def test_api_key_tablename():
    assert ApiKey.__tablename__ == 'api_key'


def test_api_key_has_required_columns():
    col_names = {c.name for c in ApiKey.__table__.columns}
    assert {
        'id',
        'user_id',
        'org_id',
        'name',
        'prefix',
        'key_hash',
        'salt',
        'is_active',
        'created_at',
        'updated_at',
    }.issubset(col_names)


def test_api_key_prefix_column():
    """Prefix is the first 8 chars of the key for identification (sk-aai-XXXXXXXX)."""
    prefix_col = ApiKey.__table__.columns['prefix']
    assert prefix_col is not None


def test_api_key_is_active_defaults_true():
    col = ApiKey.__table__.columns['is_active']
    assert col.default.arg is True

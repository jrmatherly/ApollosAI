from apollosai.storage.models.role import Role


def test_role_tablename():
    assert Role.__tablename__ == 'role'


def test_role_has_required_columns():
    col_names = {c.name for c in Role.__table__.columns}
    assert 'id' in col_names
    assert 'name' in col_names
    assert 'rank' in col_names
    assert 'created_at' in col_names
    assert 'updated_at' in col_names

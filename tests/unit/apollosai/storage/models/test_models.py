from apollosai.storage.models.organization import Organization
from apollosai.storage.models.team import Team
from apollosai.storage.models.user import User
from apollosai.storage.models.org_membership import OrgMembership
from apollosai.storage.models.team_membership import TeamMembership


def test_organization_tablename():
    assert Organization.__tablename__ == 'organization'


def test_organization_has_required_columns():
    col_names = {c.name for c in Organization.__table__.columns}
    assert {'id', 'name', 'default_llm_model', 'default_llm_base_url',
            'default_max_iterations', 'agent', 'mcp_config',
            'created_at', 'updated_at'}.issubset(col_names)


def test_team_tablename():
    assert Team.__tablename__ == 'team'


def test_team_has_org_fk():
    col_names = {c.name for c in Team.__table__.columns}
    assert 'org_id' in col_names


def test_team_has_timestamps():
    col_names = {c.name for c in Team.__table__.columns}
    assert 'created_at' in col_names
    assert 'updated_at' in col_names


def test_user_tablename():
    assert User.__tablename__ == 'user'


def test_user_has_entra_oid():
    col_names = {c.name for c in User.__table__.columns}
    assert 'entra_oid' in col_names


def test_org_membership_composite_pk():
    pk_cols = {c.name for c in OrgMembership.__table__.primary_key.columns}
    assert pk_cols == {'org_id', 'user_id'}


def test_team_membership_composite_pk():
    pk_cols = {c.name for c in TeamMembership.__table__.primary_key.columns}
    assert pk_cols == {'team_id', 'user_id'}

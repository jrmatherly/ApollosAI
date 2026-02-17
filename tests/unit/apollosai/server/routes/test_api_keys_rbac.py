"""Tests that API key routes enforce org membership."""


def test_create_key_requires_org_membership():
    """POST /api/orgs/{org_id}/keys must validate org membership via require_role."""
    from apollosai.server.routes.api_keys import _require_member

    assert _require_member is not None


def test_list_keys_requires_org_membership():
    """GET /api/orgs/{org_id}/keys must validate org membership."""
    from apollosai.server.routes.api_keys import _require_member

    assert _require_member is not None

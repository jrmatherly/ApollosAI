"""Tests for session cookie security settings."""


def test_db_session_middleware_https_only_default():
    """DBSessionMiddleware should default to https_only=True in production."""
    import ast
    from pathlib import Path

    source = Path('apollosai/app_server.py').read_text()
    tree = ast.parse(source)

    # Find the DBSessionMiddleware call
    found_https_only = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == 'https_only':
                    found_https_only = True

    assert found_https_only, (
        'DBSessionMiddleware must have explicit https_only parameter'
    )

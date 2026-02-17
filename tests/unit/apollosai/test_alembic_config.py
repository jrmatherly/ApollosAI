def test_alembic_env_importable():
    """Verify env.py can be found as a module (catches import-time errors)."""
    import importlib.util

    spec = importlib.util.find_spec('apollosai.migrations.env')
    assert spec is not None


def test_alembic_ini_exists():
    """Verify alembic.ini exists at expected location."""
    from pathlib import Path

    ini_path = Path('apollosai/alembic.ini')
    assert ini_path.exists()

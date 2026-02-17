from fastapi import FastAPI
from fastapi.testclient import TestClient

from apollosai.server.routes.health import router


def test_health_returns_200():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get('/health')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'


def test_ready_returns_503_when_db_not_initialized(monkeypatch):
    monkeypatch.setattr(
        'apollosai.server.routes.health.get_session_maker', lambda: None
    )
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    resp = client.get('/ready')
    assert resp.status_code == 503
    assert resp.json()['status'] == 'not_ready'

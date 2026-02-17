import apollosai.monitoring.otel as otel_mod
from apollosai.monitoring.otel import init_otel, shutdown_otel


def test_otel_init_noop_without_endpoint(monkeypatch):
    """OTEL init should no-op when endpoint is not set."""
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
    otel_mod._initialized = False
    init_otel()
    assert not otel_mod._initialized


def test_otel_shutdown_noop_when_not_initialized():
    """Shutdown should be safe when not initialized."""
    otel_mod._initialized = False
    shutdown_otel()  # should not raise


def test_otel_init_idempotent(monkeypatch):
    """Multiple init calls should not error."""
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_ENDPOINT', raising=False)
    otel_mod._initialized = False
    init_otel()
    init_otel()  # second call should be safe
    assert not otel_mod._initialized

"""OpenTelemetry tracer and meter provider initialization."""

import logging
import os
import threading

logger = logging.getLogger(__name__)

_initialized = False
_init_lock = threading.Lock()


def init_otel(service_name: str = 'apollosai') -> None:
    """Initialize OTEL tracer and meter providers.

    Reads OTEL_EXPORTER_OTLP_ENDPOINT from env (default: empty/disabled).
    No-ops if endpoint is empty or if already initialized.
    Supports OTEL_TRACES_SAMPLER_ARG env var for production sampling
    (default: 10% trace sampling).
    """
    global _initialized
    with _init_lock:
        if _initialized:
            return

    endpoint = os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT', '').strip()
    if not endpoint:
        logger.info('OTEL_EXPORTER_OTLP_ENDPOINT not set — skipping OTEL init')
        return

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import (
            ParentBased,
            TraceIdRatioBased,
        )

        resource = Resource.create({'service.name': service_name})

        sampler_arg = float(os.environ.get('OTEL_TRACES_SAMPLER_ARG', '0.1'))
        sampler = ParentBased(root=TraceIdRatioBased(sampler_arg))

        # Tracer
        tracer_provider = TracerProvider(resource=resource, sampler=sampler)
        tracer_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        )
        trace.set_tracer_provider(tracer_provider)

        # Meter
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=endpoint)
        )
        meter_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(meter_provider)

        with _init_lock:
            _initialized = True
        logger.info(
            'OTEL initialized — exporting to %s (sampling: %s)',
            endpoint,
            sampler_arg,
        )
    except ImportError:
        logger.warning('OTEL SDK packages not installed — skipping')
    except Exception:
        logger.exception('Failed to initialize OTEL')


def shutdown_otel() -> None:
    """Flush and shut down OTEL providers."""
    global _initialized
    with _init_lock:
        if not _initialized:
            return
        _initialized = False
    try:
        from opentelemetry import metrics, trace

        tp = trace.get_tracer_provider()
        if hasattr(tp, 'shutdown'):
            tp.shutdown()
        mp = metrics.get_meter_provider()
        if hasattr(mp, 'shutdown'):
            mp.shutdown()
    except Exception:
        logger.exception('Error shutting down OTEL')

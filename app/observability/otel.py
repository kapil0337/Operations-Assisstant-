"""OpenTelemetry instrumentation.

Initialises a TracerProvider with an OTLP HTTP exporter when OTEL_ENDPOINT is
set.  When unconfigured the module is a complete no-op — every call returns a
null tracer whose span context manager is a no-op.

Usage:
    from app.observability.otel import get_tracer, record_llm_call

    with get_tracer().start_as_current_span("supervisor") as span:
        span.set_attribute("session_id", state["session_id"])
        ...
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_tracer = None
_initialized = False


def _init() -> None:
    global _tracer, _initialized
    if _initialized:
        return
    _initialized = True

    from app.config import get_settings
    settings = get_settings()

    if not settings.otel_enabled:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": settings.otel_service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(__name__)
        logger.info("OTel tracer initialised → %s", settings.otel_endpoint)
    except Exception as exc:
        logger.warning("OTel init failed (running without traces): %s", exc)


class _NullSpan:
    def set_attribute(self, *_a, **_kw): pass
    def record_exception(self, *_a, **_kw): pass
    def set_status(self, *_a, **_kw): pass
    def __enter__(self): return self
    def __exit__(self, *_a): pass


class _NullTracer:
    def start_as_current_span(self, name: str, **_kw):
        return _NullSpan()


def get_tracer():
    _init()
    if _tracer is None:
        return _NullTracer()
    return _tracer


def instrument_fastapi(app) -> None:
    """Call once in lifespan to attach OTel middleware to FastAPI."""
    from app.config import get_settings
    if not get_settings().otel_enabled:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except Exception as exc:
        logger.warning("FastAPI OTel instrumentation failed: %s", exc)

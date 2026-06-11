"""Env-gated OpenTelemetry tracing (issue #96).

Zero overhead unless ``OTEL_ENABLED`` is true and an OTLP endpoint is set. When
enabled, FastAPI requests are auto-instrumented and spans export over OTLP/HTTP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

    from app.config import Settings


def configure_otel(app: FastAPI, settings: Settings) -> bool:
    """Instrument the app when tracing is enabled. Returns whether it was set up."""
    if not settings.otel_enabled or not settings.otel_exporter_otlp_endpoint:
        return False

    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.environment,
        }
    )
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    # Don't trace the health/readiness probes — they'd dominate the trace volume.
    FastAPIInstrumentor.instrument_app(app, excluded_urls="health,healthz,readyz")
    return True

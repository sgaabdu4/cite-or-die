from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from cite_or_die.core.config import Settings


def setup_tracing(app: FastAPI, settings: Settings) -> None:
    if not settings.otel_enabled:
        return
    if getattr(app.state, "tracing_configured", False):
        return
    provider = TracerProvider(resource=Resource.create({"service.name": "cite-or-die"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    app.state.tracing_configured = True

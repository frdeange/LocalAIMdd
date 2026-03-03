"""
Speech Service — OpenTelemetry Configuration
=============================================
Same pattern as other services. Activates when OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

import os
import logging

logger = logging.getLogger(__name__)

OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


def configure_telemetry() -> None:
    if not OTLP_ENDPOINT:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — telemetry disabled")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        resource = Resource.create({
            "service.name": "speech-service",
            "service.version": "0.1.0",
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
        })

        exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument()
        except ImportError:
            pass

        logger.info("OTel configured: speech-service → %s", OTLP_ENDPOINT)
    except Exception as e:
        logger.warning("Failed to configure OTel: %s", e)

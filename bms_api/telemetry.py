"""
BMS API — OpenTelemetry Configuration
=======================================
Configures TracerProvider + OTLP exporter + FastAPI auto-instrumentation.
Activates only when OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

import os
import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "bms-api")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


def configure_telemetry() -> None:
    """Set up OTel TracerProvider and FastAPI auto-instrumentation."""
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
            "service.name": SERVICE_NAME,
            "service.version": "0.1.0",
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
        })

        exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI (if package is installed)
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument()
            logger.info("FastAPI auto-instrumentation enabled")
        except ImportError:
            logger.debug("opentelemetry-instrumentation-fastapi not installed — skipping")

        logger.info(
            "OTel configured: service=%s endpoint=%s", SERVICE_NAME, OTLP_ENDPOINT
        )
    except ImportError as e:
        logger.warning("OTel packages not installed, telemetry disabled: %s", e)
    except Exception as e:
        logger.warning("Failed to configure OTel: %s", e)

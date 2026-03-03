"""
BMS Operations — OpenTelemetry Configuration
=============================================
Configures TracerProvider with OTLP gRPC exporter.

Activation is automatic and conditional:
- If OTEL_EXPORTER_OTLP_ENDPOINT is set → traces export to that endpoint
- If not set → no exporter, traces silently discarded (zero overhead)

Import this module EARLY (before MAF/FastMCP) so the TracerProvider
is registered before any library creates spans.

Usage:
    import src.telemetry  # noqa: F401 — side-effect import
"""

import os
import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "bms-operations")
OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


def _configure_telemetry() -> None:
    """Set up OTel TracerProvider if OTLP endpoint is configured."""
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

        logger.info(
            "OpenTelemetry configured: service=%s endpoint=%s",
            SERVICE_NAME, OTLP_ENDPOINT,
        )
    except ImportError as e:
        logger.warning("OTel packages not installed, telemetry disabled: %s", e)
    except Exception as e:
        logger.warning("Failed to configure OTel telemetry: %s", e)


# Auto-configure on import
_configure_telemetry()

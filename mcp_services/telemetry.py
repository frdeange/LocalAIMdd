"""
MCP Services — Shared OpenTelemetry Configuration
===================================================
Import this module in each MCP server to configure OTel export.
Activates only when OTEL_EXPORTER_OTLP_ENDPOINT is set.
"""

import os
import logging

logger = logging.getLogger(__name__)

OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")


def configure_telemetry(service_name: str) -> None:
    """Set up OTel TracerProvider for an MCP service."""
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
            "service.name": service_name,
            "service.version": "0.1.0",
            "deployment.environment": os.getenv("OTEL_ENVIRONMENT", "development"),
        })

        exporter = OTLPSpanExporter(endpoint=OTLP_ENDPOINT, insecure=True)
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        trace.set_tracer_provider(provider)

        logger.info(
            "OTel configured: service=%s endpoint=%s", service_name, OTLP_ENDPOINT
        )
    except ImportError as e:
        logger.warning("OTel packages not installed: %s", e)
    except Exception as e:
        logger.warning("Failed to configure OTel: %s", e)

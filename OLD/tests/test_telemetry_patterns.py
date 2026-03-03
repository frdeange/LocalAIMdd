"""
Telemetry Pattern Tests
=======================
Validates that the project follows the required telemetry patterns
to ensure reliable OpenTelemetry data export.

These tests catch the most common telemetry setup mistakes:
1. Missing OTLP exporter package in requirements
2. Correct Aspire Dashboard configuration in docker-compose
3. MCP server auto-instrumentation and OTLP export config
4. API server auto-instrumentation setup
5. Environment config for OTEL variables
"""

import os
import re

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestOtlpExporterPackage:
    """Ensure the OTLP exporter package is in requirements.txt."""

    def test_otlp_grpc_exporter_in_requirements(self) -> None:
        """requirements.txt must include the OTLP gRPC exporter."""
        path = os.path.join(BASE_DIR, "requirements.txt")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "opentelemetry-exporter-otlp-proto-grpc" in content, (
            "requirements.txt must include opentelemetry-exporter-otlp-proto-grpc."
        )


class TestShutdownTelemetryPattern:
    """Ensure shutdown_telemetry() is properly defined."""

    def test_shutdown_telemetry_is_importable(self) -> None:
        from src.telemetry import shutdown_telemetry
        assert callable(shutdown_telemetry)

    def test_shutdown_telemetry_has_force_flush(self) -> None:
        import inspect
        from src.telemetry import shutdown_telemetry
        source = inspect.getsource(shutdown_telemetry)
        assert "force_flush" in source

    def test_shutdown_telemetry_has_shutdown(self) -> None:
        import inspect
        from src.telemetry import shutdown_telemetry
        source = inspect.getsource(shutdown_telemetry)
        assert ".shutdown()" in source


class TestAspireDashboardConfig:
    """Ensure docker-compose.yml configures Aspire Dashboard correctly."""

    def _read_compose(self) -> str:
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_aspire_dashboard_service_exists(self) -> None:
        content = self._read_compose()
        assert "aspire-dashboard:" in content

    def test_aspire_ui_port(self) -> None:
        content = self._read_compose()
        assert "18888:18888" in content

    def test_aspire_otlp_grpc_port(self) -> None:
        content = self._read_compose()
        assert "4317:18889" in content

    def test_aspire_anonymous_access(self) -> None:
        content = self._read_compose()
        assert "DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true" in content


class TestEnvConfiguration:
    """Ensure .env.example has the required OTEL variables."""

    def _read_env_example(self) -> str:
        path = os.path.join(BASE_DIR, ".env.example")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_otel_endpoint_configured(self) -> None:
        content = self._read_env_example()
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in content

    def test_otel_service_name_configured(self) -> None:
        content = self._read_env_example()
        assert "OTEL_SERVICE_NAME" in content


class TestMcpServerTelemetryConfig:
    """Ensure the MCP server container is instrumented with OpenTelemetry."""

    def _read_mcp_requirements(self) -> str:
        path = os.path.join(BASE_DIR, "mcp_server", "requirements.txt")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_mcp_dockerfile(self) -> str:
        path = os.path.join(BASE_DIR, "mcp_server", "Dockerfile")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_compose(self) -> str:
        path = os.path.join(BASE_DIR, "docker-compose.yml")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_otel_distro_in_mcp_requirements(self) -> None:
        content = self._read_mcp_requirements()
        assert "opentelemetry-distro" in content

    def test_otel_exporter_in_mcp_requirements(self) -> None:
        content = self._read_mcp_requirements()
        assert "opentelemetry-exporter-otlp" in content

    def test_dockerfile_runs_bootstrap(self) -> None:
        content = self._read_mcp_dockerfile()
        assert "opentelemetry-bootstrap" in content

    def test_dockerfile_uses_otel_instrument_cmd(self) -> None:
        content = self._read_mcp_dockerfile()
        assert "opentelemetry-instrument" in content

    def test_mcp_service_has_otel_service_name(self) -> None:
        content = self._read_compose()
        assert "OTEL_SERVICE_NAME=travel-mcp-tools" in content

    def test_mcp_service_has_otel_endpoint(self) -> None:
        content = self._read_compose()
        assert "aspire-dashboard:18889" in content

    def test_mcp_service_depends_on_aspire(self) -> None:
        content = self._read_compose()
        assert "depends_on" in content


class TestApiServerTelemetryConfig:
    """Ensure the API server is instrumented with OpenTelemetry."""

    def _read_api_requirements(self) -> str:
        path = os.path.join(BASE_DIR, "api", "requirements.txt")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _read_api_dockerfile(self) -> str:
        path = os.path.join(BASE_DIR, "api", "Dockerfile")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_otel_distro_in_api_requirements(self) -> None:
        content = self._read_api_requirements()
        assert "opentelemetry-distro" in content

    def test_fastapi_instrumentation_in_api_requirements(self) -> None:
        content = self._read_api_requirements()
        assert "opentelemetry-instrumentation-fastapi" in content

    def test_api_dockerfile_uses_otel_instrument(self) -> None:
        content = self._read_api_dockerfile()
        assert "opentelemetry-instrument" in content

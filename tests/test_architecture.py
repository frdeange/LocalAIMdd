"""
Architecture Compliance Tests
=============================
Validates that the project adheres to the approved architecture.
Uses source-file reading (not imports) to avoid agent_framework dependency.
"""

import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(self_or_path, *parts):
    """Helper: read a file given path parts relative to BASE_DIR."""
    if isinstance(self_or_path, str):
        # Called as _read("path", "to", "file")
        parts = (self_or_path,) + parts
    path = os.path.join(BASE_DIR, *parts)
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestProjectStructure:
    """Verify project directory layout matches architecture spec."""

    def test_src_package_exists(self) -> None:
        assert os.path.isdir(os.path.join(BASE_DIR, "src"))
        assert os.path.isfile(os.path.join(BASE_DIR, "src", "__init__.py"))

    def test_agents_package_exists(self) -> None:
        agents_dir = os.path.join(BASE_DIR, "src", "agents")
        assert os.path.isdir(agents_dir)
        assert os.path.isfile(os.path.join(agents_dir, "__init__.py"))

    def test_workflows_package_exists(self) -> None:
        wf_dir = os.path.join(BASE_DIR, "src", "workflows")
        assert os.path.isdir(wf_dir)
        assert os.path.isfile(os.path.join(wf_dir, "__init__.py"))

    def test_mcp_server_directory_exists(self) -> None:
        mcp_dir = os.path.join(BASE_DIR, "mcp_server")
        assert os.path.isdir(mcp_dir)
        assert os.path.isfile(os.path.join(mcp_dir, "server.py"))
        assert os.path.isfile(os.path.join(mcp_dir, "Dockerfile"))

    def test_api_package_exists(self) -> None:
        api_dir = os.path.join(BASE_DIR, "api")
        assert os.path.isdir(api_dir)
        assert os.path.isfile(os.path.join(api_dir, "__init__.py"))
        assert os.path.isfile(os.path.join(api_dir, "main.py"))
        assert os.path.isfile(os.path.join(api_dir, "Dockerfile"))

    def test_api_models_package_exists(self) -> None:
        models_dir = os.path.join(BASE_DIR, "api", "models")
        assert os.path.isdir(models_dir)
        for f in ("__init__.py", "database.py", "orm.py", "schemas.py"):
            assert os.path.isfile(os.path.join(models_dir, f))

    def test_api_routes_package_exists(self) -> None:
        routes_dir = os.path.join(BASE_DIR, "api", "routes")
        assert os.path.isdir(routes_dir)
        for f in ("__init__.py", "conversations.py", "messages.py", "health.py"):
            assert os.path.isfile(os.path.join(routes_dir, f))

    def test_api_services_package_exists(self) -> None:
        svc_dir = os.path.join(BASE_DIR, "api", "services")
        assert os.path.isdir(svc_dir)
        for f in ("__init__.py", "workflow.py", "session.py"):
            assert os.path.isfile(os.path.join(svc_dir, f))

    def test_frontend_directory_exists(self) -> None:
        fe_dir = os.path.join(BASE_DIR, "frontend")
        assert os.path.isdir(fe_dir)
        assert os.path.isfile(os.path.join(fe_dir, "package.json"))
        assert os.path.isfile(os.path.join(fe_dir, "Dockerfile"))
        assert os.path.isfile(os.path.join(fe_dir, "next.config.mjs"))

    def test_config_module_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "src", "config.py"))

    def test_telemetry_module_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "src", "telemetry.py"))

    def test_docker_compose_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "docker-compose.yml"))

    def test_env_example_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, ".env.example"))

    def test_prototypes_directory_exists(self) -> None:
        assert os.path.isdir(os.path.join(BASE_DIR, "prototypes"))

    def test_scripts_directory_exists(self) -> None:
        assert os.path.isdir(os.path.join(BASE_DIR, "scripts"))
        assert os.path.isfile(os.path.join(BASE_DIR, "scripts", "init-ollama.sh"))


class TestAgentDefinitions:
    """Verify each agent module exposes the expected factory function (via source)."""

    def test_researcher_has_factory(self) -> None:
        src = _read("src", "agents", "researcher.py")
        assert "def create_researcher_agent" in src

    def test_weather_analyst_has_factory(self) -> None:
        src = _read("src", "agents", "weather_analyst.py")
        assert "def create_weather_analyst_agent" in src

    def test_planner_has_factory(self) -> None:
        src = _read("src", "agents", "planner.py")
        assert "def create_planner_agent" in src

    def test_agents_init_exports_all(self) -> None:
        src = _read("src", "agents", "__init__.py")
        assert "create_researcher_agent" in src
        assert "create_weather_analyst_agent" in src
        assert "create_planner_agent" in src


class TestWorkflowDefinitions:
    """Verify workflow module exposes the builder function (via source)."""

    def test_travel_planner_has_builder(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        assert "def build_travel_planner_workflow" in src

    def test_workflows_init_exports_builder(self) -> None:
        src = _read("src", "workflows", "__init__.py")
        assert "build_travel_planner_workflow" in src


class TestConfigModule:
    """Verify configuration module works correctly."""

    def test_settings_class_exists(self) -> None:
        from src.config import Settings
        assert Settings is not None

    def test_get_settings_returns_settings(self) -> None:
        from src.config import Settings, get_settings
        s = get_settings()
        assert isinstance(s, Settings)

    def test_settings_has_required_fields(self) -> None:
        from src.config import get_settings
        s = get_settings()
        for field in ("ollama_host", "ollama_model_id", "mcp_server_url",
                       "otel_endpoint", "otel_service_name", "api_host",
                       "api_port", "cors_origins", "database_url"):
            assert hasattr(s, field), f"Settings missing field: {field}"

    def test_settings_defaults_are_sensible(self) -> None:
        from src.config import get_settings
        s = get_settings()
        assert "8090" in s.mcp_server_url
        assert "ollama" in s.ollama_host.lower() or "11434" in s.ollama_host


class TestTelemetryModule:
    """Verify telemetry module exports expected symbols."""

    def test_setup_telemetry_callable(self) -> None:
        from src.telemetry import setup_telemetry
        assert callable(setup_telemetry)

    def test_trace_workflow_is_context_manager(self) -> None:
        from src.telemetry import trace_workflow
        ctx = trace_workflow("test", "test query")
        assert hasattr(ctx, "__enter__") and hasattr(ctx, "__exit__")

    def test_trace_agent_is_context_manager(self) -> None:
        from src.telemetry import trace_agent
        ctx = trace_agent("test_agent")
        assert hasattr(ctx, "__enter__") and hasattr(ctx, "__exit__")

    def test_record_mcp_tool_call_callable(self) -> None:
        from src.telemetry import record_mcp_tool_call
        assert callable(record_mcp_tool_call)


class TestMCPServerModule:
    """Verify MCP server defines expected tools."""

    def test_mcp_server_imports(self) -> None:
        import mcp_server.server as srv
        assert hasattr(srv, "mcp")

    def test_mcp_tools_registered(self) -> None:
        import mcp_server.server as srv
        for fn in ("get_weather", "get_current_time", "search_restaurants"):
            assert hasattr(srv, fn), f"MCP server missing {fn}"

    def test_get_weather_function(self) -> None:
        from mcp_server.server import get_weather
        assert "°C" in get_weather("Tokyo")

    def test_get_current_time_function(self) -> None:
        from mcp_server.server import get_current_time
        assert "UTC" in get_current_time("UTC")

    def test_search_restaurants_function(self) -> None:
        from mcp_server.server import search_restaurants
        assert "Tokyo" in search_restaurants("Tokyo", "Japanese")


class TestDockerCompose:
    """Verify docker-compose.yml defines required services."""

    def _read_compose(self) -> str:
        return _read("docker-compose.yml")

    def test_has_mcp_server(self) -> None:
        c = self._read_compose()
        assert "mcp-server:" in c and "8090:8090" in c

    def test_has_aspire_dashboard(self) -> None:
        c = self._read_compose()
        assert "aspire-dashboard:" in c and "18888:18888" in c

    def test_has_ollama(self) -> None:
        c = self._read_compose()
        assert "ollama" in c and "11434:11434" in c

    def test_has_postgres(self) -> None:
        c = self._read_compose()
        assert "postgres:" in c and "5432:5432" in c

    def test_has_api(self) -> None:
        c = self._read_compose()
        assert "api:" in c and "8000:8000" in c

    def test_has_frontend(self) -> None:
        c = self._read_compose()
        assert "frontend:" in c and "3000:3000" in c

    def test_has_otlp_enabled(self) -> None:
        c = self._read_compose()
        assert "DOTNET_DASHBOARD_UNSECURED_ALLOW_ANONYMOUS=true" in c


class TestArchitectureConstraints:
    """Validate architectural decisions are enforced in code (via source reading)."""

    def test_workflow_uses_sequential_builder(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        assert "SequentialBuilder" in src

    def test_weather_agent_uses_mcp_streamable_http(self) -> None:
        src = _read("src", "agents", "weather_analyst.py")
        assert "MCPStreamableHTTPTool" in src

    def test_three_agents_in_workflow(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        for name in ("researcher", "weather_analyst", "planner", "participants="):
            assert name in src, f"Missing '{name}' in travel_planner.py"

    def test_no_container_per_agent(self) -> None:
        agents_dir = os.path.join(BASE_DIR, "src", "agents")
        for filename in os.listdir(agents_dir):
            assert filename != "Dockerfile"

    def test_dockerfiles_in_expected_locations(self) -> None:
        for sub in ("mcp_server", "api", "frontend"):
            assert os.path.isfile(os.path.join(BASE_DIR, sub, "Dockerfile"))

    def test_config_uses_env_vars(self) -> None:
        src = _read("src", "config.py")
        assert "os.getenv" in src

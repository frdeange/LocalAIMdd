"""
Workflow Pattern Tests
======================
Validates workflow patterns using source-file reading to avoid
agent_framework dependency.
"""

import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    path = os.path.join(BASE_DIR, *parts)
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestSequentialWorkflowPattern:
    """Verify travel_planner.py follows the SequentialBuilder pattern."""

    def test_imports_sequential_builder(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        assert "SequentialBuilder" in src

    def test_has_builder_function(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        assert "def build_travel_planner_workflow" in src

    def test_uses_participants(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        assert "participants=" in src

    def test_chains_three_agents(self) -> None:
        src = _read("src", "workflows", "travel_planner.py")
        for agent in ("researcher", "weather_analyst", "planner"):
            assert agent in src, f"Missing {agent} in workflow"


class TestAgentFactoryPatterns:
    """Verify agent modules follow the factory function pattern."""

    @pytest.mark.parametrize("agent,factory", [
        ("researcher", "create_researcher_agent"),
        ("weather_analyst", "create_weather_analyst_agent"),
        ("planner", "create_planner_agent"),
    ])
    def test_agent_has_factory_function(self, agent: str, factory: str) -> None:
        src = _read("src", "agents", f"{agent}.py")
        assert f"def {factory}" in src

    def test_agents_use_as_agent_pattern(self) -> None:
        for agent in ("researcher", "weather_analyst", "planner"):
            src = _read("src", "agents", f"{agent}.py")
            assert "as_agent" in src, f"{agent}.py missing as_agent() call"


class TestMCPToolPattern:
    """Verify weather_analyst uses MCPStreamableHTTPTool."""

    def test_weather_analyst_imports_mcp_tool(self) -> None:
        src = _read("src", "agents", "weather_analyst.py")
        assert "MCPStreamableHTTPTool" in src

    def test_weather_analyst_passes_tools(self) -> None:
        src = _read("src", "agents", "weather_analyst.py")
        assert "tools=" in src

    def test_other_agents_no_tools(self) -> None:
        for agent in ("researcher", "planner"):
            src = _read("src", "agents", f"{agent}.py")
            assert "MCPStreamableHTTPTool" not in src


class TestApiEntryPoint:
    """Verify API server main.py includes essential patterns."""

    def test_api_uses_fastapi(self) -> None:
        src = _read("api", "main.py")
        assert "FastAPI" in src

    def test_api_defines_lifespan(self) -> None:
        src = _read("api", "main.py")
        assert "lifespan" in src

    def test_api_configures_cors(self) -> None:
        src = _read("api", "main.py")
        assert "CORS" in src or "cors" in src.lower()

    def test_api_uses_config(self) -> None:
        src = _read("api", "main.py")
        assert "get_settings" in src or "Settings" in src or "config" in src.lower()

    def test_api_uses_ollama_client(self) -> None:
        src = _read("api", "main.py")
        assert "OllamaChatClient" in src or "ollama" in src.lower()

    def test_api_includes_routes(self) -> None:
        src = _read("api", "main.py")
        assert "include_router" in src

    def test_api_messages_route_uses_workflow(self) -> None:
        src = _read("api", "routes", "messages.py")
        assert "run_workflow_sse" in src or "workflow" in src.lower()


class TestWorkflowServicePattern:
    """Verify api/services/workflow.py provides SSE streaming."""

    def test_workflow_service_exists(self) -> None:
        assert os.path.isfile(os.path.join(BASE_DIR, "api", "services", "workflow.py"))

    def test_workflow_service_uses_sequential_builder(self) -> None:
        src = _read("api", "services", "workflow.py")
        assert "build_travel_planner_workflow" in src or "SequentialBuilder" in src

    def test_workflow_service_emits_sse_events(self) -> None:
        src = _read("api", "services", "workflow.py")
        for event in ("workflow_started", "agent_started",
                       "agent_completed", "workflow_completed"):
            assert event in src, f"Missing SSE event: {event}"

    def test_workflow_service_handles_errors(self) -> None:
        src = _read("api", "services", "workflow.py")
        assert "error" in src.lower()
        assert "except" in src or "try" in src

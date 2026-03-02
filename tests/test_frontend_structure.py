"""
Frontend Structure Tests
========================
Tests that validate the React/Next.js frontend structure and configuration.
These are structural/compliance tests — no Node.js runtime needed.
"""

import json
import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")


class TestFrontendProjectStructure:
    """Verify frontend directory layout."""

    def test_package_json_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "package.json"))

    def test_tsconfig_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "tsconfig.json"))

    def test_next_config_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "next.config.mjs"))

    def test_tailwind_config_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "tailwind.config.ts"))

    def test_dockerfile_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, "Dockerfile"))

    def test_dockerignore_exists(self) -> None:
        assert os.path.isfile(os.path.join(FRONTEND_DIR, ".dockerignore"))


class TestFrontendComponents:
    """Verify expected React components are present."""

    COMPONENTS_DIR = os.path.join(FRONTEND_DIR, "src", "components")

    def test_chat_component_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.COMPONENTS_DIR, "Chat.tsx"))

    def test_message_bubble_component_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.COMPONENTS_DIR, "MessageBubble.tsx"))

    def test_conversation_list_component_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.COMPONENTS_DIR, "ConversationList.tsx"))

    def test_pipeline_status_component_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.COMPONENTS_DIR, "PipelineStatus.tsx"))


class TestFrontendLib:
    """Verify frontend lib modules are present and correct."""

    LIB_DIR = os.path.join(FRONTEND_DIR, "src", "lib")

    def test_api_client_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.LIB_DIR, "api.ts"))

    def test_types_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.LIB_DIR, "types.ts"))


class TestFrontendHooks:
    """Verify custom hooks are present."""

    HOOKS_DIR = os.path.join(FRONTEND_DIR, "src", "hooks")

    def test_use_sse_hook_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.HOOKS_DIR, "useSSE.ts"))


class TestFrontendApp:
    """Verify Next.js App Router pages are present."""

    APP_DIR = os.path.join(FRONTEND_DIR, "src", "app")

    def test_layout_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.APP_DIR, "layout.tsx"))

    def test_page_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.APP_DIR, "page.tsx"))

    def test_globals_css_exists(self) -> None:
        assert os.path.isfile(os.path.join(self.APP_DIR, "globals.css"))


class TestPackageJson:
    """Verify package.json has required dependencies."""

    def _load_package_json(self) -> dict:
        path = os.path.join(FRONTEND_DIR, "package.json")
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_has_next_dependency(self) -> None:
        pkg = self._load_package_json()
        assert "next" in pkg.get("dependencies", {})

    def test_has_react_dependency(self) -> None:
        pkg = self._load_package_json()
        assert "react" in pkg.get("dependencies", {})

    def test_has_react_markdown_dependency(self) -> None:
        pkg = self._load_package_json()
        assert "react-markdown" in pkg.get("dependencies", {})

    def test_has_typescript_devdependency(self) -> None:
        pkg = self._load_package_json()
        assert "typescript" in pkg.get("devDependencies", {})

    def test_has_tailwindcss_devdependency(self) -> None:
        pkg = self._load_package_json()
        assert "tailwindcss" in pkg.get("devDependencies", {})

    def test_has_build_script(self) -> None:
        pkg = self._load_package_json()
        assert "build" in pkg.get("scripts", {})

    def test_has_dev_script(self) -> None:
        pkg = self._load_package_json()
        assert "dev" in pkg.get("scripts", {})


class TestNextConfig:
    """Verify Next.js configuration."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(FRONTEND_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_standalone_output(self) -> None:
        """Next.js must be configured with standalone output for Docker."""
        content = self._read_file("next.config.mjs")
        assert "standalone" in content


class TestFrontendDockerfile:
    """Verify frontend Dockerfile patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(FRONTEND_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_dockerfile_is_multi_stage(self) -> None:
        content = self._read_file("Dockerfile")
        assert content.count("FROM ") >= 2

    def test_dockerfile_has_healthcheck(self) -> None:
        content = self._read_file("Dockerfile")
        assert "HEALTHCHECK" in content

    def test_dockerfile_exposes_port_3000(self) -> None:
        content = self._read_file("Dockerfile")
        assert "3000" in content

    def test_dockerfile_uses_node_image(self) -> None:
        content = self._read_file("Dockerfile")
        assert "node:" in content


class TestFrontendApiClient:
    """Verify API client patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(FRONTEND_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_api_client_uses_env_var(self) -> None:
        """API URL should be configurable via NEXT_PUBLIC_API_URL."""
        content = self._read_file("src", "lib", "api.ts")
        assert "NEXT_PUBLIC_API_URL" in content

    def test_api_client_has_conversation_functions(self) -> None:
        content = self._read_file("src", "lib", "api.ts")
        assert "createConversation" in content
        assert "listConversations" in content
        assert "getConversation" in content
        assert "deleteConversation" in content

    def test_api_client_has_send_message(self) -> None:
        content = self._read_file("src", "lib", "api.ts")
        assert "sendMessage" in content


class TestFrontendTypes:
    """Verify TypeScript type definitions."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(FRONTEND_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_types_define_conversation_interfaces(self) -> None:
        content = self._read_file("src", "lib", "types.ts")
        assert "ConversationSummary" in content
        assert "ConversationResponse" in content
        assert "MessageResponse" in content

    def test_types_define_sse_events(self) -> None:
        content = self._read_file("src", "lib", "types.ts")
        assert "WorkflowStartedEvent" in content
        assert "AgentStartedEvent" in content
        assert "AgentCompletedEvent" in content
        assert "WorkflowCompletedEvent" in content

    def test_types_define_agent_pipeline(self) -> None:
        content = self._read_file("src", "lib", "types.ts")
        assert "AGENT_PIPELINE" in content
        assert "Researcher" in content
        assert "WeatherAnalyst" in content
        assert "Planner" in content

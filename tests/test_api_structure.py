"""
API Structure Tests
===================
Tests that validate the FastAPI API server structure and patterns.
These are structural/compliance tests — no running server needed.
"""

import json
import os

import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestApiModuleStructure:
    """Verify API module structure and imports."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_api_main_creates_app(self) -> None:
        content = self._read_file("api", "main.py")
        assert "FastAPI" in content
        assert "app" in content

    def test_api_main_includes_health_route(self) -> None:
        content = self._read_file("api", "main.py")
        assert "health" in content.lower()

    def test_api_main_includes_conversation_routes(self) -> None:
        content = self._read_file("api", "main.py")
        assert "conversations" in content.lower()

    def test_api_main_includes_message_routes(self) -> None:
        content = self._read_file("api", "main.py")
        assert "messages" in content.lower()

    def test_api_main_has_lifespan(self) -> None:
        """API should use lifespan for startup/shutdown."""
        content = self._read_file("api", "main.py")
        assert "lifespan" in content

    def test_api_main_has_cors(self) -> None:
        content = self._read_file("api", "main.py")
        assert "CORSMiddleware" in content


class TestDatabaseModels:
    """Verify ORM models follow expected patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_orm_defines_conversation_model(self) -> None:
        content = self._read_file("api", "models", "orm.py")
        assert "class Conversation" in content
        assert "conversations" in content  # table name

    def test_orm_defines_message_model(self) -> None:
        content = self._read_file("api", "models", "orm.py")
        assert "class Message" in content
        assert "messages" in content  # table name

    def test_orm_uses_sqlalchemy(self) -> None:
        content = self._read_file("api", "models", "orm.py")
        assert "sqlalchemy" in content
        assert "mapped_column" in content

    def test_database_module_has_session_factory(self) -> None:
        content = self._read_file("api", "models", "database.py")
        assert "async_sessionmaker" in content or "session" in content.lower()

    def test_database_module_has_init_db(self) -> None:
        content = self._read_file("api", "models", "database.py")
        assert "init_db" in content


class TestSchemas:
    """Verify Pydantic schemas are properly defined."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_schemas_define_conversation_create(self) -> None:
        content = self._read_file("api", "models", "schemas.py")
        assert "class ConversationCreate" in content

    def test_schemas_define_conversation_response(self) -> None:
        content = self._read_file("api", "models", "schemas.py")
        assert "class ConversationResponse" in content

    def test_schemas_define_message_create(self) -> None:
        content = self._read_file("api", "models", "schemas.py")
        assert "class MessageCreate" in content

    def test_schemas_define_sse_events(self) -> None:
        content = self._read_file("api", "models", "schemas.py")
        assert "WorkflowStartedEvent" in content
        assert "AgentStartedEvent" in content
        assert "AgentCompletedEvent" in content
        assert "WorkflowCompletedEvent" in content
        assert "WorkflowErrorEvent" in content

    def test_schemas_use_pydantic(self) -> None:
        content = self._read_file("api", "models", "schemas.py")
        assert "BaseModel" in content
        assert "pydantic" in content


class TestRoutePatterns:
    """Verify route modules follow expected patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_conversations_route_has_crud(self) -> None:
        content = self._read_file("api", "routes", "conversations.py")
        assert "@router.post" in content
        assert "@router.get" in content
        assert "@router.delete" in content

    def test_messages_route_has_post(self) -> None:
        content = self._read_file("api", "routes", "messages.py")
        assert "@router.post" in content

    def test_messages_route_uses_streaming_response(self) -> None:
        content = self._read_file("api", "routes", "messages.py")
        assert "StreamingResponse" in content

    def test_messages_route_uses_sse_format(self) -> None:
        content = self._read_file("api", "routes", "messages.py")
        assert "text/event-stream" in content or "event_stream" in content

    def test_health_route_exists(self) -> None:
        content = self._read_file("api", "routes", "health.py")
        assert "@router.get" in content
        assert "health" in content.lower()


class TestServicePatterns:
    """Verify service modules follow expected patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_workflow_service_is_async_generator(self) -> None:
        content = self._read_file("api", "services", "workflow.py")
        assert "async def" in content
        assert "yield" in content

    def test_workflow_service_maps_agent_events(self) -> None:
        content = self._read_file("api", "services", "workflow.py")
        assert "agent_started" in content
        assert "agent_completed" in content

    def test_session_service_builds_context(self) -> None:
        content = self._read_file("api", "services", "session.py")
        assert "context" in content.lower()
        assert "async def" in content


class TestApiDockerfile:
    """Verify API Dockerfile patterns."""

    def _read_file(self, *parts: str) -> str:
        path = os.path.join(BASE_DIR, *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_api_dockerfile_has_healthcheck(self) -> None:
        content = self._read_file("api", "Dockerfile")
        assert "HEALTHCHECK" in content

    def test_api_dockerfile_exposes_port(self) -> None:
        content = self._read_file("api", "Dockerfile")
        assert "EXPOSE" in content
        assert "8000" in content

    def test_api_dockerfile_uses_otel_instrument(self) -> None:
        content = self._read_file("api", "Dockerfile")
        assert "opentelemetry-instrument" in content

    def test_api_dockerfile_uses_uvicorn(self) -> None:
        content = self._read_file("api", "Dockerfile")
        assert "uvicorn" in content

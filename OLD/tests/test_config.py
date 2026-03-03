"""
Configuration Tests
===================
Tests for the configuration module (Ollama + multi-service architecture).
"""

import os

import pytest

from src.config import Settings, get_settings


class TestSettings:
    """Tests for the Settings dataclass."""

    def test_default_values(self) -> None:
        s = Settings()
        assert s.ollama_host is not None
        assert s.ollama_model_id is not None
        assert s.mcp_server_url is not None
        assert s.otel_endpoint is not None
        assert s.otel_service_name is not None
        assert s.database_url is not None

    def test_mcp_server_url_default(self) -> None:
        s = Settings()
        assert "8090" in s.mcp_server_url

    def test_ollama_host_default(self) -> None:
        s = Settings()
        assert "11434" in s.ollama_host

    def test_database_url_default(self) -> None:
        s = Settings()
        assert "postgresql" in s.database_url
        assert "asyncpg" in s.database_url

    def test_settings_is_frozen(self) -> None:
        s = Settings()
        with pytest.raises(AttributeError):
            s.ollama_host = "changed"  # type: ignore[misc]


class TestGetSettings:
    """Tests for the get_settings factory function."""

    def test_returns_settings_instance(self) -> None:
        s = get_settings()
        assert isinstance(s, Settings)

    def test_reads_ollama_host_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_HOST", "http://custom-ollama:11434")
        s = get_settings()
        assert s.ollama_host == "http://custom-ollama:11434"

    def test_reads_ollama_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OLLAMA_MODEL_ID", "llama3.2")
        s = get_settings()
        assert s.ollama_model_id == "llama3.2"

    def test_reads_mcp_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MCP_SERVER_URL", "http://custom:9999/mcp")
        s = get_settings()
        assert s.mcp_server_url == "http://custom:9999/mcp"

    def test_reads_database_url_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
        s = get_settings()
        assert s.database_url == "postgresql+asyncpg://u:p@h:5432/db"

    def test_reads_cors_origins_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CORS_ORIGINS", "http://example.com,http://other.com")
        s = get_settings()
        assert "example.com" in s.cors_origins

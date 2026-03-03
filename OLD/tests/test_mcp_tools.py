"""
MCP Server Integration Tests
=============================
Tests for the FastMCP travel tools server (can run without Docker).
"""

import pytest

from mcp_server.server import get_current_time, get_weather, search_restaurants


class TestGetWeather:
    """Tests for the get_weather tool."""

    def test_known_city(self) -> None:
        result = get_weather("Seattle")
        assert "Seattle" in result
        assert "12°C" in result

    def test_known_city_case_insensitive(self) -> None:
        result = get_weather("TOKYO")
        assert "22°C" in result

    def test_unknown_city_returns_default(self) -> None:
        result = get_weather("Atlantis")
        assert "Atlantis" in result
        assert "18°C" in result  # default

    def test_partial_match(self) -> None:
        result = get_weather("Downtown Madrid")
        assert "28°C" in result

    @pytest.mark.parametrize(
        "city",
        ["seattle", "madrid", "amsterdam", "tokyo", "london", "paris", "barcelona", "rome", "berlin"],
    )
    def test_all_known_cities(self, city: str) -> None:
        result = get_weather(city)
        assert city.lower() not in result.lower() or "°C" in result


class TestGetCurrentTime:
    """Tests for the get_current_time tool."""

    def test_utc(self) -> None:
        result = get_current_time("UTC")
        assert "UTC" in result

    def test_valid_timezone(self) -> None:
        result = get_current_time("Europe/Madrid")
        assert "Europe/Madrid" in result

    def test_invalid_timezone_fallback(self) -> None:
        result = get_current_time("Invalid/Zone")
        assert "UTC" in result or "not resolved" in result


class TestSearchRestaurants:
    """Tests for the search_restaurants tool."""

    def test_known_combination(self) -> None:
        result = search_restaurants("Madrid", "Italian")
        assert "Trattoria Malatesta" in result

    def test_known_combination_tokyo(self) -> None:
        result = search_restaurants("Tokyo", "Japanese")
        assert "Sukiyabashi Jiro" in result

    def test_unknown_combination_returns_generated(self) -> None:
        result = search_restaurants("Reykjavik", "Icelandic")
        assert "Icelandic" in result
        assert "Reykjavik" in result

    def test_case_insensitive(self) -> None:
        result = search_restaurants("MADRID", "SPANISH")
        assert "Botín" in result

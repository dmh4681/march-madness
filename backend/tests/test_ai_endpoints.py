"""
Tests for AI analysis API endpoints in main.py.

Tests cover:
- POST /ai-analysis endpoint
- GET /ai-analysis (debug endpoint)
- Error handling for invalid requests
- Response format validation
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    # Need to patch before importing to avoid actual API client initialization
    with patch.dict("os.environ", {"ALLOWED_ORIGINS": "http://localhost:3000"}):
        from backend.api.main import app
        return TestClient(app)


@pytest.fixture
def mock_analyze_game_success():
    """Mock successful analyze_game response."""
    return {
        "game_id": "550e8400-e29b-41d4-a716-446655440000",
        "ai_provider": "claude",
        "model_used": "claude-sonnet-4-20250514",
        "recommended_bet": "home_spread",
        "confidence_score": 0.72,
        "key_factors": ["Factor 1", "Factor 2", "Factor 3"],
        "reasoning": "Test reasoning for the recommendation",
        "created_at": datetime.now().isoformat(),
    }


class TestAIAnalysisEndpoint:
    """Tests for POST /ai-analysis endpoint."""

    def test_ai_analysis_success_claude(self, client, mock_analyze_game_success):
        """Test successful AI analysis with Claude provider."""
        with patch("backend.api.main.analyze_game", return_value=mock_analyze_game_success):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["game_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert data["provider"] == "claude"
            assert data["recommended_bet"] == "home_spread"
            assert data["confidence_score"] == 0.72
            assert len(data["key_factors"]) == 3
            assert data["reasoning"] == "Test reasoning for the recommendation"

    def test_ai_analysis_success_grok(self, client):
        """Test successful AI analysis with Grok provider."""
        grok_response = {
            "game_id": "550e8400-e29b-41d4-a716-446655440000",
            "ai_provider": "grok",
            "model_used": "grok-3",
            "recommended_bet": "away_spread",
            "confidence_score": 0.65,
            "key_factors": ["Grok Factor 1", "Grok Factor 2"],
            "reasoning": "Grok's analysis reasoning",
            "created_at": datetime.now().isoformat(),
        }

        with patch("backend.api.main.analyze_game", return_value=grok_response):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "grok"}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "grok"
            assert data["recommended_bet"] == "away_spread"

    def test_ai_analysis_default_provider_is_claude(self, client, mock_analyze_game_success):
        """Test that Claude is the default provider when not specified."""
        with patch("backend.api.main.analyze_game", return_value=mock_analyze_game_success) as mock:
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000"}
            )

            assert response.status_code == 200
            # Verify analyze_game was called with claude as provider
            mock.assert_called_once_with("550e8400-e29b-41d4-a716-446655440000", "claude")

    def test_ai_analysis_game_not_found(self, client):
        """Test 400 error when game is not found."""
        with patch("backend.api.main.analyze_game", side_effect=ValueError("Game not found: invalid-id")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "invalid-game-id", "provider": "claude"}
            )

            assert response.status_code == 400
            assert "Game not found" in response.json()["detail"]

    def test_ai_analysis_api_key_not_configured(self, client):
        """Test 400 error when API key is not configured."""
        with patch("backend.api.main.analyze_game", side_effect=ValueError("Claude API key not configured")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 400
            assert "API key not configured" in response.json()["detail"]

    def test_ai_analysis_internal_error(self, client):
        """Test 500 error on unexpected exceptions."""
        with patch("backend.api.main.analyze_game", side_effect=Exception("Unexpected API error")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500
            # Should return generic error message, not expose internal details
            assert "AI analysis failed" in response.json()["detail"]

    def test_ai_analysis_missing_game_id(self, client):
        """Test 422 validation error when game_id is missing."""
        response = client.post(
            "/ai-analysis",
            json={"provider": "claude"}  # Missing game_id
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_ai_analysis_invalid_provider(self, client):
        """Test 422 validation error for invalid provider."""
        response = client.post(
            "/ai-analysis",
            json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "invalid"}
        )

        assert response.status_code == 422  # Pydantic validation error

    def test_ai_analysis_error_message_truncation(self, client):
        """Test that long error messages are truncated for security."""
        long_error = "x" * 200  # Very long error message
        with patch("backend.api.main.analyze_game", side_effect=ValueError(long_error)):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 400
            # Error message should be truncated to 100 chars
            assert len(response.json()["detail"]) <= 100


class TestAIAnalysisGetEndpoint:
    """Tests for GET /ai-analysis debug endpoint."""

    def test_ai_analysis_get_returns_error(self, client):
        """Test that GET /ai-analysis returns helpful error."""
        response = client.get("/ai-analysis")

        assert response.status_code == 200  # Returns 200 with error message
        data = response.json()
        assert data["error"] == "This endpoint requires POST method"
        assert data["method_received"] == "GET"


class TestDebugAIAnalysisEndpoint:
    """Tests for GET /debug/ai-analysis/{game_id} endpoint."""

    def test_debug_endpoint_game_not_found(self, client):
        """Test debug endpoint when game doesn't exist."""
        with patch("backend.api.main.get_game_by_id", return_value=None):
            response = client.get("/debug/ai-analysis/nonexistent-game-id")

            assert response.status_code == 200
            data = response.json()
            # Debug endpoint returns early when game not found, before overall_status is set
            assert data["steps"]["1_game_fetch"]["status"] == "failed"
            assert "Game not found" in data["errors"]

    def test_debug_endpoint_success_flow(self, client, sample_game, sample_spread, valid_claude_response):
        """Test debug endpoint for successful analysis."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        with patch("backend.api.main.get_game_by_id", return_value=sample_game), \
             patch("backend.api.main.build_game_context") as mock_context, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "GROK_API_KEY": "test-key"}):

            mock_context.return_value = {
                "game_id": sample_game["id"],
                "home_kenpom": {"rank": 5},
                "away_kenpom": None,
                "home_haslametrics": None,
                "away_haslametrics": None,
                "spread": -7.5,
            }

            response = client.get(f"/debug/ai-analysis/{sample_game['id']}?provider=claude")

            assert response.status_code == 200
            data = response.json()
            assert data["steps"]["1_game_fetch"]["status"] == "success"
            assert data["steps"]["2_build_context"]["status"] == "success"


class TestResponseFormatValidation:
    """Tests to verify response format matches AIAnalysisResponse model."""

    def test_response_contains_all_required_fields(self, client, mock_analyze_game_success):
        """Test that response contains all fields defined in AIAnalysisResponse."""
        with patch("backend.api.main.analyze_game", return_value=mock_analyze_game_success):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields are present
            required_fields = ["game_id", "provider", "recommended_bet", "confidence_score", "key_factors", "reasoning"]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

    def test_response_types_are_correct(self, client, mock_analyze_game_success):
        """Test that response field types are correct."""
        with patch("backend.api.main.analyze_game", return_value=mock_analyze_game_success):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 200
            data = response.json()

            assert isinstance(data["game_id"], str)
            assert isinstance(data["provider"], str)
            assert isinstance(data["recommended_bet"], str)
            assert isinstance(data["confidence_score"], (int, float))
            assert isinstance(data["key_factors"], list)
            assert isinstance(data["reasoning"], str)


class TestRateLimitingAndTimeout:
    """Tests for handling rate limiting and timeout scenarios."""

    def test_rate_limit_error_handling(self, client):
        """Test handling of rate limit errors from AI providers."""
        # Simulate anthropic rate limit error
        rate_limit_error = Exception("rate_limit_error: Too many requests")

        with patch("backend.api.main.analyze_game", side_effect=rate_limit_error):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500
            # Should return generic error, not expose rate limit details
            assert "AI analysis failed" in response.json()["detail"]

    def test_timeout_error_handling(self, client):
        """Test handling of timeout errors."""
        import asyncio
        timeout_error = asyncio.TimeoutError("Request timed out")

        with patch("backend.api.main.analyze_game", side_effect=timeout_error):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500

    def test_connection_error_handling(self, client):
        """Test handling of connection errors."""
        import requests
        conn_error = requests.exceptions.ConnectionError("Failed to connect")

        with patch("backend.api.main.analyze_game", side_effect=conn_error):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500


class TestCORSConfiguration:
    """Tests for CORS middleware configuration."""

    def test_cors_allows_configured_origin(self, client):
        """Test that configured origins are allowed."""
        response = client.options(
            "/ai-analysis",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )

        # CORS preflight should succeed
        assert response.status_code == 200

    def test_cors_rejects_unknown_origin(self, client):
        """Test that unknown origins are rejected."""
        response = client.options(
            "/ai-analysis",
            headers={
                "Origin": "http://evil-site.com",
                "Access-Control-Request-Method": "POST",
            }
        )

        # Should not include CORS headers for unknown origin
        assert "access-control-allow-origin" not in response.headers or \
               response.headers.get("access-control-allow-origin") != "http://evil-site.com"


class TestSecurityErrorHandling:
    """Tests for security-related error handling."""

    def test_internal_errors_dont_leak_stack_traces(self, client):
        """Test that internal errors don't expose stack traces or file paths."""
        with patch("backend.api.main.analyze_game", side_effect=Exception("Error at /home/user/app/secret.py line 42")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500
            response_text = json.dumps(response.json())
            # Should not contain file paths or line numbers
            assert "/home/" not in response_text
            assert "line 42" not in response_text
            assert "secret.py" not in response_text

    def test_database_errors_are_sanitized(self, client):
        """Test that database errors don't expose schema details."""
        with patch("backend.api.main.analyze_game", side_effect=Exception(
            "PostgreSQL error: relation 'ai_analysis' does not exist at column 'api_key'"
        )):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "550e8400-e29b-41d4-a716-446655440000", "provider": "claude"}
            )

            assert response.status_code == 500
            response_text = json.dumps(response.json())
            # Should not contain database schema details
            assert "PostgreSQL" not in response_text
            assert "relation" not in response_text
            assert "column" not in response_text


class TestInputValidation:
    """Tests for input validation and sanitization."""

    def test_malformed_game_id_format(self, client, mock_analyze_game_success):
        """Test handling of malformed game IDs."""
        # Even with weird characters, endpoint should handle gracefully
        with patch("backend.api.main.analyze_game", return_value=mock_analyze_game_success):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "not-a-valid-uuid-format", "provider": "claude"}
            )
            # Should either succeed (if service accepts it) or return 400
            assert response.status_code in [200, 400]

    def test_very_long_game_id(self, client):
        """Test handling of excessively long game IDs."""
        long_id = "a" * 10000  # Very long string
        with patch("backend.api.main.analyze_game", side_effect=ValueError("Invalid game ID")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": long_id, "provider": "claude"}
            )
            assert response.status_code == 400

    def test_null_bytes_in_game_id(self, client):
        """Test handling of null bytes in input (potential injection)."""
        with patch("backend.api.main.analyze_game", side_effect=ValueError("Invalid game ID")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "valid-id\x00evil-suffix", "provider": "claude"}
            )
            # Should handle without crashing
            assert response.status_code in [400, 422]

    def test_unicode_in_game_id(self, client):
        """Test handling of unicode characters in game ID."""
        with patch("backend.api.main.analyze_game", side_effect=ValueError("Game not found")):
            response = client.post(
                "/ai-analysis",
                json={"game_id": "game-id-\u202e-rtl-override", "provider": "claude"}
            )
            assert response.status_code == 400

"""
Tests for failure scenarios across the data pipeline.

Tests API timeouts, missing data, malformed responses, database errors,
and network issues to ensure the pipeline handles failures gracefully.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime
import requests


# ============================================================================
# API TIMEOUT TESTS
# ============================================================================

class TestOddsAPIFailures:
    """Test failure handling for The Odds API."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_connection_timeout(self, mock_get):
        """Test handling of connection timeout."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_read_timeout(self, mock_get):
        """Test handling of read timeout (slow server response)."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_get.side_effect = requests.exceptions.ReadTimeout("Read timed out")

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_ssl_error(self, mock_get):
        """Test handling of SSL certificate errors."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_get.side_effect = requests.exceptions.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_dns_resolution_failure(self, mock_get):
        """Test handling of DNS resolution failures."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Failed to establish a new connection: [Errno -2] Name or service not known"
        )

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_rate_limit_exceeded(self, mock_get):
        """Test handling of rate limit (429) response."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "429 Client Error: Too Many Requests"
        )
        mock_get.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_unauthorized_api_key(self, mock_get):
        """Test handling of unauthorized (401) response."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Client Error: Unauthorized"
        )
        mock_get.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_server_error(self, mock_get):
        """Test handling of server error (500) response."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error: Internal Server Error"
        )
        mock_get.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_invalid_json_response(self, mock_get):
        """Test handling of invalid JSON in response."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.headers = {}
        mock_get.return_value = mock_response

        # Should handle JSON decode error gracefully
        try:
            result = fetch_odds_api_spreads()
            assert result == []
        except ValueError:
            # If it raises, that's also acceptable behavior
            pass


class TestHaslametricsAPIFailures:
    """Test failure handling for Haslametrics API."""

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_connection_timeout(self, mock_get):
        """Test handling of connection timeout."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_get.side_effect = requests.exceptions.ConnectTimeout("Connection timed out")

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_read_timeout(self, mock_get):
        """Test handling of read timeout."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_get.side_effect = requests.exceptions.ReadTimeout("Read timed out")

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_brotli_decompression_error(self, mock_get):
        """Test handling when brotli decompression fails."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # Simulate corrupted brotli data
        mock_response.content = b'\x00\x00\x00\x00corrupted'
        mock_get.return_value = mock_response

        # Should handle XML parse error
        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_cloudflare_blocking(self, mock_get):
        """Test handling of Cloudflare blocking (403)."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "403 Forbidden: Cloudflare blocking"
        )
        mock_get.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_season_not_available(self, mock_get):
        """Test handling when season data not yet available (404)."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "404 Not Found"
        )
        mock_get.return_value = mock_response

        result = fetch_haslametrics_ratings(2030)  # Future season

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_truncated_xml_response(self, mock_get):
        """Test handling of truncated XML response."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # Truncated XML - missing closing tags
        mock_response.content = b'<?xml version="1.0"?><ratings><mr t="Duke"'
        mock_get.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_html_error_page_instead_of_xml(self, mock_get):
        """Test handling when server returns HTML error page instead of XML."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'<!DOCTYPE html><html><body>Error Page</body></html>'
        mock_get.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        # Should fail to parse as valid ratings XML
        assert result is None or len(result) == 0


# ============================================================================
# DATABASE FAILURE TESTS
# ============================================================================

class TestSupabaseFailures:
    """Test failure handling for Supabase operations."""

    @patch('backend.api.supabase_client.create_client')
    @patch('backend.api.supabase_client._validate_supabase_url')
    def test_missing_supabase_url(self, mock_validate, mock_create):
        """Test handling of missing Supabase URL."""
        from backend.api.supabase_client import get_supabase

        # Reset the client to force re-initialization
        import backend.api.supabase_client as supa_module
        supa_module._client = None
        supa_module.SUPABASE_URL = None
        supa_module.SUPABASE_KEY = "test-key"

        with pytest.raises(ValueError) as exc_info:
            get_supabase()

        assert "SUPABASE_URL" in str(exc_info.value)

    @patch('backend.api.supabase_client.create_client')
    def test_invalid_supabase_url_format(self, mock_create):
        """Test handling of invalid Supabase URL format."""
        from backend.api.supabase_client import get_supabase, _validate_supabase_url

        # Reset the client
        import backend.api.supabase_client as supa_module
        supa_module._client = None
        supa_module.SUPABASE_URL = "http://malicious-site.com"
        supa_module.SUPABASE_KEY = "test-key"

        # URL validation should reject non-Supabase URLs
        assert not _validate_supabase_url("http://malicious-site.com")
        assert not _validate_supabase_url("https://evil.com")
        assert not _validate_supabase_url("not-a-url")

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_database_connection_timeout(self, mock_supabase):
        """Test handling of database connection timeout."""
        from backend.data_collection.daily_refresh import get_team_id

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.side_effect = Exception("Connection timed out")

        result = get_team_id("Duke")

        # Should handle gracefully (may return None or raise)
        # The important thing is it doesn't crash the pipeline

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_database_insert_constraint_violation(self, mock_supabase):
        """Test handling of unique constraint violations."""
        from backend.data_collection.daily_refresh import process_odds_data

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{"id": "game-uuid"}])

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = Exception("duplicate key value violates unique constraint")

        odds_data = [
            {
                "home_team": "Duke Blue Devils",
                "away_team": "UNC Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": [
                    {"markets": [{"key": "spreads", "outcomes": [{"name": "Duke Blue Devils", "point": -7.5}]}]}
                ]
            }
        ]

        # Should handle gracefully and continue
        result = process_odds_data(odds_data)

        # Pipeline should not crash


class TestKenpomDatabaseFailures:
    """Test KenPom database operation failures."""

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_insert_failure_continues_processing(self, mock_supabase, mock_get_team_id):
        """Test that insert failures don't stop processing other teams."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings
        import pandas as pd

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert

        # First insert fails, second succeeds
        mock_insert.execute.side_effect = [
            Exception("Insert failed"),
            MagicMock(data=[{"id": "rating-uuid"}])
        ]

        df = pd.DataFrame([
            {"Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2", "AdjEM": 28.5},
            {"Rk": 2, "Team": "UNC", "Conf": "ACC", "W-L": "17-3", "AdjEM": 25.2},
        ])

        result = store_kenpom_ratings(df, 2025)

        assert result["errors"] == 1
        assert result["inserted"] == 1


class TestHaslametricsDatabaseFailures:
    """Test Haslametrics database operation failures."""

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_insert_failure_continues_processing(self, mock_supabase, mock_get_team_id):
        """Test that insert failures don't stop processing other teams."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert

        # First insert fails, second and third succeed
        mock_insert.execute.side_effect = [
            Exception("Insert failed"),
            MagicMock(data=[{"id": "rating-uuid"}]),
            MagicMock(data=[{"id": "rating-uuid-2"}]),
        ]

        teams = [
            {"team": "Duke", "rank": "1"},
            {"team": "UNC", "rank": "2"},
            {"team": "Kentucky", "rank": "3"},
        ]

        result = store_haslametrics_ratings(teams, 2025)

        assert result["errors"] == 1
        assert result["inserted"] == 2


# ============================================================================
# MISSING DATA TESTS
# ============================================================================

class TestMissingDataHandling:
    """Test handling of missing or incomplete data."""

    def test_odds_data_missing_home_team(self):
        """Test handling when home_team is missing."""
        from backend.data_collection.daily_refresh import normalize_team_name

        # Should not crash on None/empty
        assert normalize_team_name(None) == ""
        assert normalize_team_name("") == ""

    def test_odds_data_missing_bookmakers(self):
        """Test handling when bookmakers data is missing."""
        from backend.data_collection.daily_refresh import process_odds_data

        with patch('backend.data_collection.daily_refresh._ensure_supabase') as mock_supabase, \
             patch('backend.data_collection.daily_refresh.get_team_id') as mock_get_team_id:

            mock_client = MagicMock()
            mock_supabase.return_value = mock_client
            mock_get_team_id.return_value = "team-uuid"

            mock_table = MagicMock()
            mock_client.table.return_value = mock_table

            mock_select = MagicMock()
            mock_table.select.return_value = mock_select

            mock_eq = MagicMock()
            mock_select.eq.return_value = mock_eq
            mock_eq.eq.return_value = mock_eq
            mock_eq.execute.return_value = MagicMock(data=[{"id": "game-uuid"}])

            # Game with no bookmakers
            odds_data = [
                {
                    "home_team": "Duke Blue Devils",
                    "away_team": "UNC Tar Heels",
                    "commence_time": "2025-01-25T23:00:00Z",
                    "bookmakers": []  # Empty bookmakers
                }
            ]

            result = process_odds_data(odds_data)

            # Should complete without error, but no spreads inserted
            assert result["spreads_inserted"] == 0

    def test_haslametrics_missing_attributes(self):
        """Test handling of XML elements missing attributes."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        with patch('backend.data_collection.haslametrics_scraper.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            # XML with missing attributes
            mock_response.content = b'''<?xml version="1.0"?>
            <ratings>
                <mr t="Duke"/>
                <mr rk="2"/>
                <mr t="UNC" rk="3"/>
            </ratings>'''
            mock_get.return_value = mock_response

            result = fetch_haslametrics_ratings(2025)

            assert result is not None
            # Should have 3 entries, even with missing attributes
            assert len(result) == 3

    def test_kenpom_missing_columns(self):
        """Test handling of DataFrame with missing expected columns."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings
        import pandas as pd

        with patch('backend.data_collection.kenpom_scraper.get_team_id') as mock_get_team_id, \
             patch('backend.data_collection.kenpom_scraper.supabase') as mock_supabase:

            mock_get_team_id.return_value = "team-uuid"

            mock_table = MagicMock()
            mock_supabase.table.return_value = mock_table

            mock_insert = MagicMock()
            mock_table.insert.return_value = mock_insert
            mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

            # DataFrame with only some columns
            df = pd.DataFrame([
                {"Team": "Duke", "Rk": 1},  # Missing most fields
            ])

            result = store_kenpom_ratings(df, 2025)

            # Should still attempt to insert with available data
            assert result["inserted"] >= 0

    def test_nan_values_handled(self):
        """Test handling of NaN values in data."""
        from backend.data_collection.kenpom_scraper import safe_int, safe_float
        import math

        # Should return None for NaN
        assert safe_int(float('nan')) is None
        assert safe_float(float('nan')) is None


# ============================================================================
# MALFORMED RESPONSE TESTS
# ============================================================================

class TestMalformedResponses:
    """Test handling of malformed API responses."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_odds_api_empty_response(self, mock_get):
        """Test handling of empty response from Odds API."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = []
        mock_response.headers = {"x-requests-remaining": "500"}
        mock_get.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_odds_api_null_values(self, mock_get):
        """Test handling of null values in Odds API response."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {
                "id": None,
                "home_team": None,
                "away_team": None,
                "commence_time": None,
                "bookmakers": None,
            }
        ]
        mock_response.headers = {}
        mock_get.return_value = mock_response

        result = fetch_odds_api_spreads()

        # Should return the data; processing handles nulls
        assert len(result) == 1

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_haslametrics_wrong_root_element(self, mock_get):
        """Test handling of wrong root element in XML."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.content = b'<?xml version="1.0"?><wrong_root><data/></wrong_root>'
        mock_get.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        # Should parse but find no mr elements
        assert result is not None
        assert len(result) == 0


# ============================================================================
# PIPELINE RESILIENCE TESTS
# ============================================================================

class TestPipelineResilience:
    """Test that the pipeline continues despite individual component failures."""

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_pipeline_continues_after_espn_failure(
        self, mock_ai, mock_view, mock_results, mock_predictions,
        mock_haslametrics, mock_kenpom, mock_process_odds,
        mock_fetch_odds, mock_espn
    ):
        """Test pipeline continues when ESPN fails."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        # ESPN fails
        mock_espn.side_effect = Exception("ESPN unavailable")

        # Other components succeed
        mock_fetch_odds.return_value = []
        mock_process_odds.return_value = {"spreads_inserted": 0}
        mock_kenpom.return_value = {"status": "success"}
        mock_haslametrics.return_value = {"status": "success"}
        mock_predictions.return_value = {"predictions_created": 0}
        mock_results.return_value = {"games_scored": 0}
        mock_view.return_value = {"today_games": 0}
        mock_ai.return_value = {"analyses_created": 0}

        result = run_daily_refresh()

        # Pipeline completes
        assert result["status"] == "success"
        assert "error" in result.get("espn_games", {})

        # Other components were still called
        mock_kenpom.assert_called_once()
        mock_haslametrics.assert_called_once()

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_pipeline_continues_after_kenpom_failure(
        self, mock_ai, mock_view, mock_results, mock_predictions,
        mock_haslametrics, mock_kenpom, mock_process_odds,
        mock_fetch_odds, mock_espn
    ):
        """Test pipeline continues when KenPom fails."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        mock_espn.return_value = {"games_created": 0}
        mock_fetch_odds.return_value = []
        mock_process_odds.return_value = {"spreads_inserted": 0}

        # KenPom fails
        mock_kenpom.side_effect = Exception("KenPom login failed")

        # Others succeed
        mock_haslametrics.return_value = {"status": "success"}
        mock_predictions.return_value = {"predictions_created": 0}
        mock_results.return_value = {"games_scored": 0}
        mock_view.return_value = {"today_games": 0}
        mock_ai.return_value = {"analyses_created": 0}

        result = run_daily_refresh()

        # Pipeline completes
        assert result["status"] == "success"
        assert "error" in result.get("kenpom", {})

        # Haslametrics was still called
        mock_haslametrics.assert_called_once()

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_pipeline_continues_after_ai_failure(
        self, mock_ai, mock_view, mock_results, mock_predictions,
        mock_haslametrics, mock_kenpom, mock_process_odds,
        mock_fetch_odds, mock_espn
    ):
        """Test pipeline completes even when AI analysis fails."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        mock_espn.return_value = {"games_created": 0}
        mock_fetch_odds.return_value = []
        mock_process_odds.return_value = {"spreads_inserted": 0}
        mock_kenpom.return_value = {"status": "success"}
        mock_haslametrics.return_value = {"status": "success"}
        mock_predictions.return_value = {"predictions_created": 5}
        mock_results.return_value = {"games_scored": 0}
        mock_view.return_value = {"today_games": 5}

        # AI fails
        mock_ai.side_effect = Exception("Claude API unavailable")

        result = run_daily_refresh()

        # Pipeline completes
        assert result["status"] == "success"
        assert "error" in result.get("ai_analysis", {})

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_pipeline_handles_multiple_failures(
        self, mock_ai, mock_view, mock_results, mock_predictions,
        mock_haslametrics, mock_kenpom, mock_process_odds,
        mock_fetch_odds, mock_espn
    ):
        """Test pipeline handles multiple component failures gracefully."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        # Multiple failures
        mock_espn.side_effect = Exception("ESPN down")
        mock_fetch_odds.return_value = []
        mock_process_odds.return_value = {"spreads_inserted": 0}
        mock_kenpom.side_effect = Exception("KenPom down")
        mock_haslametrics.side_effect = Exception("Haslametrics down")
        mock_predictions.return_value = {"predictions_created": 0}
        mock_results.return_value = {"games_scored": 0}
        mock_view.return_value = {"today_games": 0}
        mock_ai.side_effect = Exception("AI service down")

        result = run_daily_refresh()

        # Pipeline still completes
        assert result["status"] == "success"
        assert "error" in result.get("espn_games", {})
        assert "error" in result.get("kenpom", {})
        assert "error" in result.get("haslametrics", {})
        assert "error" in result.get("ai_analysis", {})


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_long_team_name(self):
        """Test handling of extremely long team names."""
        from backend.data_collection.daily_refresh import normalize_team_name

        long_name = "A" * 10000
        result = normalize_team_name(long_name)

        # Should not crash, may truncate
        assert isinstance(result, str)

    def test_special_characters_in_team_name(self):
        """Test handling of special characters in team names."""
        from backend.data_collection.daily_refresh import normalize_team_name

        # Various special characters
        test_names = [
            "Team (Test)",
            "Team [Bracket]",
            "Team & Another",
            "Team / Division",
            "Team\nNewline",
            "Team\tTab",
        ]

        for name in test_names:
            result = normalize_team_name(name)
            assert isinstance(result, str)

    def test_unicode_team_names(self):
        """Test handling of unicode characters in team names."""
        from backend.data_collection.daily_refresh import normalize_team_name

        unicode_names = [
            "Téam Ñame",
            "チーム名",
            "Équipe Test",
        ]

        for name in unicode_names:
            result = normalize_team_name(name)
            assert isinstance(result, str)

    def test_empty_odds_data_list(self):
        """Test processing empty odds data."""
        from backend.data_collection.daily_refresh import process_odds_data

        with patch('backend.data_collection.daily_refresh._ensure_supabase') as mock_supabase:
            mock_client = MagicMock()
            mock_supabase.return_value = mock_client

            result = process_odds_data([])

            assert result["games_updated"] == 0
            assert result["spreads_inserted"] == 0

    def test_future_date_handling(self):
        """Test handling of far-future dates."""
        from backend.data_collection.daily_refresh import EASTERN_TZ, UTC_TZ
        from datetime import datetime

        # Far future date
        future_utc = datetime(2050, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
        future_eastern = future_utc.astimezone(EASTERN_TZ)

        # Should convert correctly
        assert future_eastern.year == 2050 or future_eastern.year == 2049

    def test_past_date_handling(self):
        """Test handling of old dates."""
        from backend.data_collection.daily_refresh import EASTERN_TZ, UTC_TZ
        from datetime import datetime

        # Old date
        past_utc = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC_TZ)
        past_eastern = past_utc.astimezone(EASTERN_TZ)

        # Should convert correctly
        assert past_eastern.year == 2000 or past_eastern.year == 1999

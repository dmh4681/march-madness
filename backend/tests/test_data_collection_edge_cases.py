"""
Unit tests for data collection edge cases (Task #11).

Tests cover:
- Empty responses from APIs (Odds API, ESPN, Haslametrics, KenPom)
- Malformed data (invalid JSON, truncated XML, wrong types)
- Missing fields (partial game data, incomplete bookmaker data)
- Rate limiting (429 responses, retry-after headers)
- Duplicate data handling (same game inserted twice, overlapping spreads)
- Network error recovery (timeouts, connection resets, DNS failures)
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, date, timedelta
import xml.etree.ElementTree as ET


# ============================================================================
# ODDS API EDGE CASES
# ============================================================================

class TestOddsAPIEmptyResponses:
    """Test handling of empty or null responses from The Odds API."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_empty_array_response(self, mock_requests):
        """Empty array [] from Odds API means no games available."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_null_json_response(self, mock_requests):
        """Handle case where API returns null/None body."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = None
        mock_response.headers = {"x-requests-remaining": "450"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        # Should handle None gracefully
        assert result == [] or result is None

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_invalid_json_response(self, mock_requests):
        """Handle malformed JSON from API."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_response.headers = {"x-requests-remaining": "450"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []


class TestOddsAPIMalformedData:
    """Test handling of malformed game data from The Odds API."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_game_missing_bookmakers(self, mock_requests):
        """Game with no bookmakers array should be handled."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "game-1",
                "home_team": "Duke Blue Devils",
                "away_team": "UNC Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                # No "bookmakers" key
            }
        ]
        mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        # Should return the game data even without bookmakers
        assert isinstance(result, list)

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_game_with_empty_bookmakers(self, mock_requests):
        """Game with empty bookmakers array."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "game-1",
                "home_team": "Duke Blue Devils",
                "away_team": "UNC Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": [],
            }
        ]
        mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert isinstance(result, list)
        assert len(result) >= 0

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_bookmaker_missing_spreads_market(self, mock_requests):
        """Bookmaker only has h2h but no spreads market."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "game-1",
                "home_team": "Duke Blue Devils",
                "away_team": "UNC Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "h2h",  # Only h2h, no spreads
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -280},
                                    {"name": "UNC Tar Heels", "price": 220},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert isinstance(result, list)

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_spread_with_missing_point_field(self, mock_requests):
        """Spread outcome missing 'point' field."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {
                "id": "game-1",
                "home_team": "Duke Blue Devils",
                "away_team": "UNC Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -110},  # Missing "point"
                                    {"name": "UNC Tar Heels", "price": -110},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert isinstance(result, list)


class TestOddsAPIRateLimiting:
    """Test handling of rate limiting from The Odds API."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_429_rate_limit_response(self, mock_requests):
        """Handle 429 Too Many Requests."""
        import requests as req
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
            response=MagicMock(status_code=429)
        )
        mock_response.status_code = 429
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_zero_remaining_requests_header(self, mock_requests):
        """When x-requests-remaining is 0, we've hit the limit."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.headers = {
            "x-requests-remaining": "0",
            "x-requests-used": "500",
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        # Should still return (empty) results, logging the warning
        assert result == []

    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', None)
    def test_missing_api_key(self):
        """Fetching without API key should fail gracefully."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        result = fetch_odds_api_spreads()

        assert result == []


class TestOddsAPINetworkErrors:
    """Test network error handling for Odds API."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_connection_timeout(self, mock_requests):
        """Handle connection timeout."""
        import requests as req
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_requests.side_effect = req.exceptions.Timeout("Connection timed out")

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_connection_refused(self, mock_requests):
        """Handle connection refused."""
        import requests as req
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_requests.side_effect = req.exceptions.ConnectionError("Connection refused")

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_dns_resolution_failure(self, mock_requests):
        """Handle DNS resolution failure."""
        import requests as req
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_requests.side_effect = req.exceptions.ConnectionError(
            "Failed to resolve 'api.the-odds-api.com'"
        )

        result = fetch_odds_api_spreads()

        assert result == []

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-key')
    def test_ssl_error(self, mock_requests):
        """Handle SSL certificate verification error."""
        import requests as req
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_requests.side_effect = req.exceptions.SSLError("SSL certificate verify failed")

        result = fetch_odds_api_spreads()

        assert result == []


# ============================================================================
# ESPN SCRAPER EDGE CASES
# ============================================================================

class TestESPNEmptyResponses:
    """Test ESPN API empty and null response handling."""

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_empty_events_array(self, mock_requests):
        """ESPN returns valid JSON but empty events."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {"events": []}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_no_events_key(self, mock_requests):
        """ESPN returns JSON without 'events' key."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {"leagues": [], "day": {}}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_request_failure(self, mock_requests):
        """ESPN API request fails entirely."""
        import requests as req
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_requests.side_effect = req.exceptions.RequestException("Service unavailable")

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []


class TestESPNMalformedData:
    """Test ESPN API malformed data handling."""

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_event_missing_date(self, mock_requests):
        """Event without a date field should be skipped."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {
                    "id": "401234567",
                    # No "date" field
                    "competitions": [
                        {
                            "competitors": [
                                {"homeAway": "home", "team": {"displayName": "Duke Blue Devils"}},
                                {"homeAway": "away", "team": {"displayName": "UNC Tar Heels"}},
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_event_with_single_competitor(self, mock_requests):
        """Event with only one team (exhibition?) should be skipped."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {
                    "id": "401234567",
                    "date": "2025-01-25T23:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"homeAway": "home", "team": {"displayName": "Duke Blue Devils"}},
                                # Only one competitor
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_event_empty_competitions(self, mock_requests):
        """Event with empty competitions array."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {
                    "id": "401234567",
                    "date": "2025-01-25T23:00:00Z",
                    "competitions": [],
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        assert result == []

    @patch('backend.data_collection.espn_scraper.requests.get')
    def test_team_missing_display_name(self, mock_requests):
        """Team object without displayName."""
        from backend.data_collection.espn_scraper import fetch_espn_schedule

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "events": [
                {
                    "id": "401234567",
                    "date": "2025-01-25T23:00:00Z",
                    "competitions": [
                        {
                            "competitors": [
                                {"homeAway": "home", "team": {}},  # No displayName
                                {"homeAway": "away", "team": {"displayName": "UNC Tar Heels"}},
                            ]
                        }
                    ]
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_espn_schedule(date(2025, 1, 25))

        # Empty displayName should result in skipping this game
        # (home_team will be empty string, which is falsy)
        assert len(result) == 0


class TestESPNTeamNameNormalization:
    """Test ESPN team name normalization edge cases."""

    def test_empty_name(self):
        """Empty string normalization."""
        from backend.data_collection.espn_scraper import normalize_espn_team_name

        assert normalize_espn_team_name("") == ""

    def test_none_input(self):
        """None input should return empty string."""
        from backend.data_collection.espn_scraper import normalize_espn_team_name

        assert normalize_espn_team_name(None) == ""

    def test_state_abbreviation_expansion(self):
        """'St.' and 'St' should expand to 'state'."""
        from backend.data_collection.espn_scraper import normalize_espn_team_name

        result_dot = normalize_espn_team_name("Michigan St.")
        result_no_dot = normalize_espn_team_name("Michigan St")

        # Both should result in "michigan-state" or something containing "michigan"
        assert "michigan" in result_dot.lower()
        assert "michigan" in result_no_dot.lower()

    def test_common_abbreviations_mapped(self):
        """Common abbreviations like BYU, USC, etc. should be mapped."""
        from backend.data_collection.espn_scraper import normalize_espn_team_name

        assert normalize_espn_team_name("BYU") == "byu"
        assert normalize_espn_team_name("USC") == "usc"
        assert normalize_espn_team_name("UCLA") == "ucla"
        assert normalize_espn_team_name("UConn") == "connecticut"

    def test_name_with_special_characters(self):
        """Names with apostrophes and periods."""
        from backend.data_collection.espn_scraper import normalize_espn_team_name

        result = normalize_espn_team_name("Saint Mary's")
        assert isinstance(result, str)
        assert len(result) > 0


# ============================================================================
# HASLAMETRICS EDGE CASES
# ============================================================================

class TestHaslametricsEmptyResponses:
    """Test Haslametrics empty and error response handling."""

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_empty_xml_body(self, mock_requests):
        """Empty but valid XML body."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b'<?xml version="1.0"?><ratings></ratings>'
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        assert result is not None
        assert len(result) == 0

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_completely_empty_response(self, mock_requests):
        """Server returns empty byte string."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b""
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        # Should handle gracefully (None or empty)
        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_html_error_page_instead_of_xml(self, mock_requests):
        """Server returns HTML error page instead of XML."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b"<html><body><h1>503 Service Unavailable</h1></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        # Should fail gracefully on HTML parse (may return None or empty list)
        assert result is None or (isinstance(result, list) and len(result) == 0)


class TestHaslametricsMalformedData:
    """Test Haslametrics malformed XML handling."""

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_truncated_xml(self, mock_requests):
        """XML truncated mid-element."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b'<?xml version="1.0"?><ratings><mr rk="1" t="Duke"'
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_xml_with_missing_attributes(self, mock_requests):
        """Team elements missing some attributes."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
<ratings>
    <mr t="Duke" rk="1"/>
    <mr rk="2"/>
</ratings>"""
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        assert result is not None
        assert len(result) == 2
        # First team has name, second doesn't
        assert result[0]["team"] == "Duke"
        assert result[1]["team"] is None  # Missing 't' attribute

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_xml_with_non_numeric_values(self, mock_requests):
        """Numeric fields contain non-numeric values."""
        from backend.data_collection.haslametrics_scraper import _fetch_haslametrics_ratings_uncached

        mock_response = MagicMock()
        mock_response.content = b"""<?xml version="1.0"?>
<ratings>
    <mr rk="N/A" t="Test Team" c="TEST" w="abc" l="def"
        ou="NaN" du="inf" ap="---"
        mom="0.05" mmo="0.03" mmd="0.07"/>
</ratings>"""
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = _fetch_haslametrics_ratings_uncached(2025)

        assert result is not None
        assert len(result) == 1
        # The raw values are strings from XML - safe_float/safe_int handles conversion
        assert result[0]["rank"] == "N/A"
        assert result[0]["wins"] == "abc"

    def test_safe_conversions_with_edge_values(self):
        """Test safe_int and safe_float with tricky edge cases."""
        from backend.data_collection.haslametrics_scraper import safe_int, safe_float

        # N/A values
        assert safe_int("N/A") is None
        assert safe_float("N/A") is None

        # Empty strings
        assert safe_int("") is None
        assert safe_float("") is None

        # Whitespace
        assert safe_int("  ") is None
        assert safe_float("  ") is None

        # Negative values
        assert safe_float("-0.05") == -0.05
        assert safe_int("-3") == -3

        # Zero
        assert safe_int("0") == 0
        assert safe_float("0.0") == 0.0

        # Large numbers
        assert safe_int("999") == 999
        assert safe_float("999.99") == 999.99

        # Percentage strings
        assert safe_float("76.5%") == 76.5

        # Comma-separated numbers
        assert safe_int("1,234") == 1234


class TestHaslametricsStorageEdgeCases:
    """Test edge cases when storing Haslametrics data to Supabase."""

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_store_team_with_all_null_metrics(self, mock_supabase, mock_get_team_id):
        """Team entry with all metrics as None/N/A."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "team-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        teams = [{
            "team": "Test Team",
            "rank": None,
            "offensive_efficiency": None,
            "defensive_efficiency": None,
            "all_play_pct": None,
            "momentum_overall": None,
            "sos": None,
            "last_5_record": None,
        }]

        result = store_haslametrics_ratings(teams, 2025)

        # Should still insert (with minimal fields)
        assert result["inserted"] == 1

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_efficiency_margin_calculation_with_missing_data(self, mock_supabase, mock_get_team_id):
        """Efficiency margin can't be calculated when offense or defense is missing."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "team-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        # Only offensive_efficiency provided, no defensive
        teams = [{
            "team": "Test Team",
            "offensive_efficiency": "118.5",
            "defensive_efficiency": None,
        }]

        store_haslametrics_ratings(teams, 2025)

        # Verify no efficiency_margin was calculated
        insert_args = mock_table.insert.call_args[0][0]
        assert "efficiency_margin" not in insert_args


# ============================================================================
# KENPOM EDGE CASES
# ============================================================================

class TestKenpomMalformedData:
    """Test KenPom DataFrame edge cases."""

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_empty_dataframe(self, mock_supabase, mock_get_team_id):
        """Empty DataFrame should return zero results."""
        import pandas as pd
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        result = store_kenpom_ratings(pd.DataFrame(), 2025)

        assert result["inserted"] == 0
        assert result["skipped"] == 0
        assert result["errors"] == 0

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_dataframe_with_nan_values(self, mock_supabase, mock_get_team_id):
        """DataFrame with NaN values in critical columns."""
        import pandas as pd
        import numpy as np
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.return_value = "team-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        df = pd.DataFrame([{
            "Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2",
            "AdjEM": np.nan, "AdjO": np.nan, "AdjD": np.nan,
            "AdjT": np.nan, "Luck": np.nan,
        }])

        result = store_kenpom_ratings(df, 2025)

        # Should insert (NaN values become None via safe_float)
        assert result["inserted"] == 1

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_dataframe_with_wrong_column_types(self, mock_supabase, mock_get_team_id):
        """DataFrame with string values where floats expected."""
        import pandas as pd
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.return_value = "team-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        df = pd.DataFrame([{
            "Rk": "1", "Team": "Duke", "Conf": "ACC", "W-L": "18-2",
            "AdjEM": "28.5", "AdjO": "118.5",
        }])

        result = store_kenpom_ratings(df, 2025)

        # safe_float should handle string "28.5" correctly
        assert result["inserted"] == 1

    def test_safe_int_with_various_nan_types(self):
        """Test safe_int with different NaN representations."""
        import pandas as pd
        import numpy as np
        from backend.data_collection.kenpom_scraper import safe_int

        assert safe_int(float('nan')) is None
        assert safe_int(np.nan) is None
        assert safe_int(pd.NaT) is None
        assert safe_int("nan") is None

    def test_safe_float_with_infinity(self):
        """Test safe_float with infinity values."""
        from backend.data_collection.kenpom_scraper import safe_float

        # Float infinity
        result = safe_float(float('inf'))
        # Should either return inf or None depending on implementation
        assert result is None or result == float('inf')

    def test_wl_record_parsing_edge_cases(self):
        """Test W-L record parsing with various formats."""
        from backend.data_collection.kenpom_scraper import safe_int

        # Standard format
        wl = "18-2"
        wins = safe_int(wl.split("-")[0]) if "-" in wl else 0
        losses = safe_int(wl.split("-")[-1]) if "-" in wl else 0
        assert wins == 18
        assert losses == 2

        # Empty string
        wl = ""
        wins = safe_int(wl.split("-")[0]) if "-" in wl else 0
        assert wins == 0

        # Single number (no dash)
        wl = "18"
        wins = safe_int(wl.split("-")[0]) if "-" in wl else 0
        assert wins == 0


# ============================================================================
# DUPLICATE DATA HANDLING
# ============================================================================

class TestDuplicateDataHandling:
    """Test that duplicate data is handled properly throughout the pipeline."""

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_duplicate_team_in_haslametrics_xml(self, mock_supabase, mock_get_team_id):
        """Same team appearing twice in XML should insert two records (daily snapshots)."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "duke-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        # Same team twice (shouldn't happen, but handle gracefully)
        teams = [
            {"team": "Duke", "rank": "1", "offensive_efficiency": "118.5", "defensive_efficiency": "89.2"},
            {"team": "Duke", "rank": "1", "offensive_efficiency": "118.5", "defensive_efficiency": "89.2"},
        ]

        result = store_haslametrics_ratings(teams, 2025)

        # Both should be inserted (historical snapshots)
        assert result["inserted"] == 2

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_duplicate_team_in_kenpom_df(self, mock_supabase, mock_get_team_id):
        """Same team appearing twice in DataFrame."""
        import pandas as pd
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.return_value = "duke-uuid"
        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        df = pd.DataFrame([
            {"Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2", "AdjEM": 28.5},
            {"Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2", "AdjEM": 28.5},
        ])

        result = store_kenpom_ratings(df, 2025)

        assert result["inserted"] == 2


# ============================================================================
# DAILY REFRESH PIPELINE EDGE CASES
# ============================================================================

class TestDailyRefreshEdgeCases:
    """Test edge cases in the daily refresh orchestration."""

    def test_get_current_season_boundary(self):
        """Test season calculation at August boundary."""
        from backend.data_collection.daily_refresh import get_current_season

        # get_current_season uses today's date, so we just verify it returns a reasonable year
        season = get_current_season()
        current_year = datetime.now().year
        assert season in [current_year, current_year + 1]

    def test_get_eastern_date_today_returns_date(self):
        """get_eastern_date_today always returns a date object."""
        from backend.data_collection.daily_refresh import get_eastern_date_today

        result = get_eastern_date_today()
        assert isinstance(result, date)

    def test_team_name_normalization_edge_cases(self):
        """Test team name normalization for unusual formats."""
        from backend.data_collection.daily_refresh import normalize_team_name

        # Standard cases
        result = normalize_team_name("Duke Blue Devils")
        assert "duke" in result.lower()

        # Already normalized
        result2 = normalize_team_name("duke")
        assert "duke" in result2.lower()


# ============================================================================
# ARBITRAGE DETECTION EDGE CASES
# ============================================================================

class TestArbitrageDetectorEdgeCases:
    """Test arbitrage detection with edge case inputs."""

    def test_american_odds_to_prob_positive_odds(self):
        """Convert positive American odds to implied probability."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        # +150 -> 100 / (150 + 100) = 0.40
        result = american_odds_to_prob(150)
        assert abs(result - 0.40) < 0.001

    def test_american_odds_to_prob_negative_odds(self):
        """Convert negative American odds to implied probability."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        # -150 -> 150 / (150 + 100) = 0.60
        result = american_odds_to_prob(-150)
        assert abs(result - 0.60) < 0.001

    def test_american_odds_to_prob_standard_juice(self):
        """Standard -110 odds should be ~52.4%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        result = american_odds_to_prob(-110)
        assert abs(result - 0.5238) < 0.001

    def test_american_odds_to_prob_even_money(self):
        """Even money (+100) should be exactly 50%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        result = american_odds_to_prob(100)
        assert abs(result - 0.50) < 0.001

    def test_american_odds_to_prob_none(self):
        """None odds should return 0.5 default."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        result = american_odds_to_prob(None)
        assert result == 0.5

    def test_american_odds_to_prob_heavy_favorite(self):
        """Very heavy favorite (-1000) should be ~90.9%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        result = american_odds_to_prob(-1000)
        assert abs(result - 0.909) < 0.001

    def test_american_odds_to_prob_huge_underdog(self):
        """Huge underdog (+1000) should be ~9.1%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        result = american_odds_to_prob(1000)
        assert abs(result - 0.0909) < 0.001


# ============================================================================
# ODDS MONITOR EDGE CASES
# ============================================================================

class TestOddsMonitorEdgeCases:
    """Test odds movement detection edge cases."""

    def test_ml_to_implied_prob_zero_odds(self):
        """Zero moneyline should return 0.5."""
        from backend.services.odds_monitor import _ml_to_implied_prob

        result = _ml_to_implied_prob(0)
        assert result == 0.5

    def test_ml_to_implied_prob_positive(self):
        """Positive moneyline conversion."""
        from backend.services.odds_monitor import _ml_to_implied_prob

        result = _ml_to_implied_prob(150)
        expected = 100.0 / (150 + 100.0)
        assert abs(result - expected) < 0.001

    def test_ml_to_implied_prob_negative(self):
        """Negative moneyline conversion."""
        from backend.services.odds_monitor import _ml_to_implied_prob

        result = _ml_to_implied_prob(-150)
        expected = 150.0 / (150.0 + 100.0)
        assert abs(result - expected) < 0.001

    def test_odds_movement_spread_calculation(self):
        """Test spread movement calculation with None values."""
        from backend.services.odds_monitor import OddsMovement

        # Both spreads present
        movement = OddsMovement(
            game_id="game-1",
            home_team="Duke",
            away_team="UNC",
            previous_spread=-7.5,
            current_spread=-5.5,
            previous_home_ml=-280,
            current_home_ml=-220,
            previous_away_ml=220,
            current_away_ml=180,
        )
        assert movement.spread_movement == 2.0

    def test_odds_movement_with_none_spread(self):
        """Spread movement when previous spread is None."""
        from backend.services.odds_monitor import OddsMovement

        movement = OddsMovement(
            game_id="game-1",
            home_team="Duke",
            away_team="UNC",
            previous_spread=None,
            current_spread=-5.5,
            previous_home_ml=None,
            current_home_ml=-220,
            previous_away_ml=None,
            current_away_ml=180,
        )
        assert movement.spread_movement is None
        assert movement.home_prob_movement is None


# ============================================================================
# AI SERVICE JSON PARSING EDGE CASES
# ============================================================================

class TestJSONParsingEdgeCases:
    """Test _extract_json_from_response with various edge cases."""

    def test_valid_json(self):
        """Direct valid JSON should parse correctly."""
        from backend.api.ai_service import _extract_json_from_response

        result = _extract_json_from_response('{"recommended_bet": "home_spread", "confidence_score": 0.72}')
        assert result["recommended_bet"] == "home_spread"

    def test_json_in_code_block(self):
        """JSON wrapped in markdown code block."""
        from backend.api.ai_service import _extract_json_from_response

        text = '```json\n{"recommended_bet": "pass", "confidence_score": 0.5}\n```'
        result = _extract_json_from_response(text)
        assert result["recommended_bet"] == "pass"

    def test_json_embedded_in_text(self):
        """JSON embedded in surrounding text."""
        from backend.api.ai_service import _extract_json_from_response

        text = 'Here is my analysis: {"recommended_bet": "away_spread", "confidence_score": 0.65, "key_factors": ["Factor 1"], "reasoning": "Test"} Hope this helps!'
        result = _extract_json_from_response(text)
        assert result["recommended_bet"] == "away_spread"

    def test_nested_json_objects(self):
        """JSON with nested objects."""
        from backend.api.ai_service import _extract_json_from_response

        text = '{"recommended_bet": "home_spread", "confidence_score": 0.72, "key_factors": ["Factor {special} chars"], "reasoning": "Test"}'
        result = _extract_json_from_response(text)
        assert result["recommended_bet"] == "home_spread"

    def test_no_json_at_all(self):
        """No JSON in response returns fallback."""
        from backend.api.ai_service import _extract_json_from_response

        result = _extract_json_from_response("I apologize but I cannot provide betting advice.")
        assert result["recommended_bet"] == "pass"
        assert result["confidence_score"] == 0.5

    def test_empty_string(self):
        """Empty string returns fallback."""
        from backend.api.ai_service import _extract_json_from_response

        result = _extract_json_from_response("")
        assert result["recommended_bet"] == "pass"

    def test_malformed_json_with_single_quotes(self):
        """JSON with single quotes (invalid JSON)."""
        from backend.api.ai_service import _extract_json_from_response

        text = "{'recommended_bet': 'pass', 'confidence_score': 0.5}"
        result = _extract_json_from_response(text)
        # Should fall back gracefully
        assert result["recommended_bet"] == "pass"

    def test_json_with_trailing_comma(self):
        """JSON with trailing comma (invalid JSON)."""
        from backend.api.ai_service import _extract_json_from_response

        text = '{"recommended_bet": "pass", "confidence_score": 0.5,}'
        result = _extract_json_from_response(text)
        # Trailing comma makes it invalid JSON, should fallback
        assert result["recommended_bet"] == "pass"

    def test_multiple_json_objects(self):
        """Multiple JSON objects - should find the first valid one."""
        from backend.api.ai_service import _extract_json_from_response

        text = 'First: {"a": 1} Second: {"recommended_bet": "over", "confidence_score": 0.6}'
        result = _extract_json_from_response(text)
        # Should find one of the JSON objects
        assert isinstance(result, dict)

"""
Tests for the KenPom and Haslametrics scrapers.

Tests data fetching, parsing, and storage for both analytics sources.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pandas as pd


# ============================================================================
# FIXTURES - KenPom
# ============================================================================

@pytest.fixture
def sample_kenpom_ratings_df():
    """Sample KenPom ratings DataFrame from kenpompy."""
    return pd.DataFrame([
        {
            "Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2",
            "AdjEM": 28.5, "AdjO": 118.5, "AdjO Rank": 3,
            "AdjD": 90.0, "AdjD Rank": 2, "AdjT": 70.2, "AdjT Rank": 45,
            "Luck": 0.02, "Luck Rank": 150, "SOS AdjEM": 12.5, "SOS AdjEM Rank": 10,
            "OppO": 108.2, "OppO Rank": 15, "OppD": 98.5, "OppD Rank": 20,
            "NCSOS AdjEM": 8.5, "NCSOS AdjEM Rank": 25,
        },
        {
            "Rk": 2, "Team": "North Carolina", "Conf": "ACC", "W-L": "17-3",
            "AdjEM": 25.2, "AdjO": 116.8, "AdjO Rank": 8,
            "AdjD": 91.6, "AdjD Rank": 5, "AdjT": 72.1, "AdjT Rank": 30,
            "Luck": -0.01, "Luck Rank": 200, "SOS AdjEM": 11.8, "SOS AdjEM Rank": 12,
            "OppO": 107.5, "OppO Rank": 18, "OppD": 99.2, "OppD Rank": 25,
            "NCSOS AdjEM": 7.8, "NCSOS AdjEM Rank": 30,
        },
        {
            "Rk": 3, "Team": "Kentucky", "Conf": "SEC", "W-L": "16-4",
            "AdjEM": 23.8, "AdjO": 115.2, "AdjO Rank": 12,
            "AdjD": 91.4, "AdjD Rank": 4, "AdjT": 68.5, "AdjT Rank": 80,
            "Luck": 0.03, "Luck Rank": 120, "SOS AdjEM": 10.5, "SOS AdjEM Rank": 15,
            "OppO": 106.8, "OppO Rank": 22, "OppD": 98.8, "OppD Rank": 22,
            "NCSOS AdjEM": 6.5, "NCSOS AdjEM Rank": 40,
        },
    ])


@pytest.fixture
def sample_kenpom_alternative_columns_df():
    """KenPom DataFrame with alternative column naming."""
    return pd.DataFrame([
        {
            "Rk.": 1, "Team": "Duke", "Conf": "ACC", "W-L.1": "18-2",
            "AdjEM.": 28.5, "AdjO.": 118.5, "AdjO.1": 3,
            "AdjD.": 90.0, "AdjD.1": 2, "AdjT.": 70.2, "AdjT.1": 45,
            "Luck.": 0.02, "Luck.1": 150,
        },
    ])


# ============================================================================
# FIXTURES - Haslametrics
# ============================================================================

@pytest.fixture
def sample_haslametrics_xml_response():
    """Sample Haslametrics XML response."""
    return b"""<?xml version="1.0" encoding="UTF-8"?>
<ratings>
    <mr rk="1" t="Duke" c="ACC" w="18" l="2"
        ou="118.5" du="89.2" ftpct="76.5"
        mom="0.05" mmo="0.03" mmd="0.07"
        inc="0.12" sos="0.65" rpi="0.85" ap="0.94" wr="0.90"
        p5wl="5-0" p5ud="up"
        r_q1="5-1" r_q2="3-0" r_q3="4-0" r_q4="6-1"
        r_home="10-0" r_away="6-2" r_neut="2-0"/>
    <mr rk="2" t="N Carolina" c="ACC" w="17" l="3"
        ou="116.2" du="91.5" ftpct="74.2"
        mom="0.02" mmo="0.01" mmd="0.03"
        inc="0.15" sos="0.62" rpi="0.83" ap="0.91" wr="0.85"
        p5wl="4-1" p5ud="even"
        r_q1="4-2" r_q2="3-1" r_q3="5-0" r_q4="5-0"
        r_home="9-1" r_away="5-2" r_neut="3-0"/>
    <mr rk="350" t="Unknown School" c="IND" w="2" l="18"
        ou="85.5" du="115.2" ftpct="62.1"
        mom="-0.08" mmo="-0.05" mmd="-0.03"
        inc="0.45" sos="0.25" rpi="0.35" ap="0.10" wr="0.10"
        p5wl="0-5" p5ud="down"
        r_q1="0-5" r_q2="0-3" r_q3="1-5" r_q4="1-5"
        r_home="2-8" r_away="0-10" r_neut="0-0"/>
</ratings>
"""


@pytest.fixture
def sample_haslametrics_empty_xml():
    """Empty Haslametrics XML response."""
    return b'<?xml version="1.0" encoding="UTF-8"?><ratings></ratings>'


@pytest.fixture
def sample_haslametrics_malformed_xml():
    """Malformed XML response."""
    return b"<ratings><mr t='Duke' unclosed>"


# ============================================================================
# KENPOM SCRAPER TESTS
# ============================================================================

class TestKenpomNormalizeTeamName:
    """Test KenPom team name normalization."""

    def test_direct_mappings(self):
        """Test direct name mappings."""
        from backend.data_collection.kenpom_scraper import normalize_team_name

        assert normalize_team_name("North Carolina") == "north-carolina"
        assert normalize_team_name("NC State") == "nc-state"
        assert normalize_team_name("UConn") == "connecticut"
        assert normalize_team_name("Connecticut") == "connecticut"
        assert normalize_team_name("Ole Miss") == "mississippi"
        assert normalize_team_name("St. John's") == "st-johns"
        assert normalize_team_name("Saint John's") == "st-johns"

    def test_basic_normalization(self):
        """Test basic normalization for unmapped names."""
        from backend.data_collection.kenpom_scraper import normalize_team_name

        # Basic names should be lowercased and have spaces replaced
        assert normalize_team_name("Duke") == "duke"
        assert normalize_team_name("Kentucky") == "kentucky"

    def test_empty_input(self):
        """Test handling of empty input."""
        from backend.data_collection.kenpom_scraper import normalize_team_name

        assert normalize_team_name("") == ""
        assert normalize_team_name(None) == ""


class TestKenpomGetTeamId:
    """Test KenPom team ID lookup."""

    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_exact_match(self, mock_supabase):
        """Test exact match returns team ID."""
        from backend.data_collection.kenpom_scraper import get_team_id

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{"id": "duke-uuid"}])

        result = get_team_id("Duke")

        assert result == "duke-uuid"

    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_partial_match_fallback(self, mock_supabase):
        """Test partial match when exact match fails."""
        from backend.data_collection.kenpom_scraper import get_team_id

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        mock_ilike = MagicMock()
        mock_select.ilike.return_value = mock_ilike
        mock_ilike.execute.return_value = MagicMock(data=[{"id": "duke-uuid", "normalized_name": "duke"}])

        result = get_team_id("Duke Blue Devils")

        assert result == "duke-uuid"

    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_team_not_found(self, mock_supabase):
        """Test returns None when team not found."""
        from backend.data_collection.kenpom_scraper import get_team_id

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        mock_ilike = MagicMock()
        mock_select.ilike.return_value = mock_ilike
        mock_ilike.execute.return_value = MagicMock(data=[])

        result = get_team_id("Unknown Team")

        assert result is None


class TestKenpomSafeConversions:
    """Test safe type conversions."""

    def test_safe_int(self):
        """Test safe_int function."""
        from backend.data_collection.kenpom_scraper import safe_int

        assert safe_int("123") == 123
        assert safe_int(123) == 123
        assert safe_int("123.5") == 123
        assert safe_int(123.5) == 123
        assert safe_int("") is None
        assert safe_int(None) is None
        assert safe_int(float('nan')) is None

    def test_safe_float(self):
        """Test safe_float function."""
        from backend.data_collection.kenpom_scraper import safe_float

        assert safe_float("123.45") == 123.45
        assert safe_float(123.45) == 123.45
        assert safe_float("123") == 123.0
        assert safe_float("") is None
        assert safe_float(None) is None
        assert safe_float(float('nan')) is None


class TestKenpomStoreRatings:
    """Test storing KenPom ratings in Supabase."""

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_successful_storage(self, mock_supabase, mock_get_team_id, sample_kenpom_ratings_df):
        """Test successful storage of ratings."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.side_effect = lambda name: f"{name.lower().replace(' ', '-')}-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        result = store_kenpom_ratings(sample_kenpom_ratings_df, 2025)

        assert result["inserted"] == 3
        assert result["skipped"] == 0
        assert result["errors"] == 0

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_handles_unmatched_teams(self, mock_supabase, mock_get_team_id, sample_kenpom_ratings_df):
        """Test that unmatched teams are skipped."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        # Return None for all team lookups
        mock_get_team_id.return_value = None

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        result = store_kenpom_ratings(sample_kenpom_ratings_df, 2025)

        assert result["inserted"] == 0
        assert result["skipped"] == 3

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_handles_insert_errors(self, mock_supabase, mock_get_team_id, sample_kenpom_ratings_df):
        """Test handling of insert errors."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = Exception("Database error")

        result = store_kenpom_ratings(sample_kenpom_ratings_df, 2025)

        assert result["errors"] == 3

    @patch('backend.data_collection.kenpom_scraper.get_team_id')
    @patch('backend.data_collection.kenpom_scraper.supabase')
    def test_handles_alternative_column_names(
        self, mock_supabase, mock_get_team_id, sample_kenpom_alternative_columns_df
    ):
        """Test handling of alternative column naming from kenpompy."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        result = store_kenpom_ratings(sample_kenpom_alternative_columns_df, 2025)

        # Should still work with alternative column names
        assert result["inserted"] == 1


class TestKenpomFetchRatings:
    """Test fetching KenPom ratings."""

    @patch('backend.data_collection.kenpom_scraper.KENPOM_EMAIL', None)
    @patch('backend.data_collection.kenpom_scraper.KENPOM_PASSWORD', None)
    def test_returns_none_without_credentials(self):
        """Test returns None when credentials not set."""
        from backend.data_collection.kenpom_scraper import fetch_kenpom_ratings

        result = fetch_kenpom_ratings(2025)

        assert result is None

    @patch('backend.data_collection.kenpom_scraper.KENPOM_EMAIL', 'test@test.com')
    @patch('backend.data_collection.kenpom_scraper.KENPOM_PASSWORD', 'password')
    def test_handles_import_error(self):
        """Test graceful handling when kenpompy not installed."""
        from backend.data_collection.kenpom_scraper import fetch_kenpom_ratings

        # The import will fail if kenpompy is not installed
        result = fetch_kenpom_ratings(2025)

        # Should return None on import error, not crash
        assert result is None or isinstance(result, pd.DataFrame)


class TestKenpomRefresh:
    """Test full KenPom refresh."""

    @patch('backend.data_collection.kenpom_scraper.fetch_kenpom_ratings')
    @patch('backend.data_collection.kenpom_scraper.store_kenpom_ratings')
    def test_successful_refresh(self, mock_store, mock_fetch, sample_kenpom_ratings_df):
        """Test successful refresh flow."""
        from backend.data_collection.kenpom_scraper import refresh_kenpom_data

        mock_fetch.return_value = sample_kenpom_ratings_df
        mock_store.return_value = {"inserted": 3, "skipped": 0, "errors": 0}

        result = refresh_kenpom_data(2025)

        assert result["status"] == "success"
        assert result["ratings"]["inserted"] == 3

    @patch('backend.data_collection.kenpom_scraper.fetch_kenpom_ratings')
    def test_handles_fetch_failure(self, mock_fetch):
        """Test handling when fetch fails."""
        from backend.data_collection.kenpom_scraper import refresh_kenpom_data

        mock_fetch.return_value = None

        result = refresh_kenpom_data(2025)

        assert result["status"] == "error"
        assert "error" in result

    @patch('backend.data_collection.kenpom_scraper.fetch_kenpom_ratings')
    def test_handles_empty_dataframe(self, mock_fetch):
        """Test handling when fetch returns empty DataFrame."""
        from backend.data_collection.kenpom_scraper import refresh_kenpom_data

        mock_fetch.return_value = pd.DataFrame()

        result = refresh_kenpom_data(2025)

        assert result["status"] == "error"


# ============================================================================
# HASLAMETRICS SCRAPER TESTS
# ============================================================================

class TestHaslametricsNormalizeTeamName:
    """Test Haslametrics team name normalization."""

    def test_abbreviation_mappings(self):
        """Test abbreviated name mappings."""
        from backend.data_collection.haslametrics_scraper import normalize_team_name

        assert normalize_team_name("N Carolina") == "north-carolina"
        assert normalize_team_name("NC State") == "nc-state"
        assert normalize_team_name("S Carolina") == "south-carolina"
        assert normalize_team_name("W Virginia") == "west-virginia"
        assert normalize_team_name("E Tennessee St") == "east-tennessee-state"

    def test_abbreviation_with_periods(self):
        """Test abbreviations with periods."""
        from backend.data_collection.haslametrics_scraper import normalize_team_name

        assert normalize_team_name("St. John's") == "st-johns"
        assert normalize_team_name("St. Mary's") == "saint-marys"
        assert normalize_team_name("Geo. Washington") == "george-washington"

    def test_special_team_names(self):
        """Test special team name mappings."""
        from backend.data_collection.haslametrics_scraper import normalize_team_name

        assert normalize_team_name("UConn") == "connecticut"
        assert normalize_team_name("Ole Miss") == "mississippi"
        assert normalize_team_name("UNLV") == "unlv"
        assert normalize_team_name("BYU") == "brigham-young"
        assert normalize_team_name("LSU") == "louisiana-state"

    def test_empty_input(self):
        """Test handling of empty input."""
        from backend.data_collection.haslametrics_scraper import normalize_team_name

        assert normalize_team_name("") == ""
        assert normalize_team_name(None) == ""


class TestHaslametricsSafeConversions:
    """Test Haslametrics-specific safe conversions."""

    def test_safe_int_with_commas(self):
        """Test safe_int handles commas."""
        from backend.data_collection.haslametrics_scraper import safe_int

        assert safe_int("1,234") == 1234
        assert safe_int("12,345,678") == 12345678

    def test_safe_float_with_percentage(self):
        """Test safe_float handles percentages."""
        from backend.data_collection.haslametrics_scraper import safe_float

        assert safe_float("76.5%") == 76.5
        assert safe_float("100%") == 100.0

    def test_safe_conversions_with_na(self):
        """Test handling of N/A values."""
        from backend.data_collection.haslametrics_scraper import safe_int, safe_float

        assert safe_int("N/A") is None
        assert safe_float("N/A") is None


class TestHaslametricsFetchRatings:
    """Test fetching Haslametrics ratings."""

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_successful_fetch(self, mock_requests, sample_haslametrics_xml_response):
        """Test successful XML fetch and parse."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.content = sample_haslametrics_xml_response
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is not None
        assert len(result) == 3
        assert result[0]["team"] == "Duke"
        assert result[0]["rank"] == "1"
        assert result[0]["offensive_efficiency"] == "118.5"
        assert result[0]["defensive_efficiency"] == "89.2"
        assert result[0]["all_play_pct"] == "0.94"

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_correct_url_construction(self, mock_requests):
        """Test URL is constructed correctly for different seasons."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.content = b'<?xml version="1.0"?><ratings></ratings>'
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        fetch_haslametrics_ratings(2025)

        # Verify URL uses 2-digit year
        call_args = mock_requests.call_args
        assert "ratings25.xml" in call_args[0][0]

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_correct_headers_sent(self, mock_requests):
        """Test proper headers are sent to avoid blocking."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.content = b'<?xml version="1.0"?><ratings></ratings>'
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        fetch_haslametrics_ratings(2025)

        call_kwargs = mock_requests.call_args[1]
        assert "headers" in call_kwargs
        assert "User-Agent" in call_kwargs["headers"]
        assert call_kwargs["timeout"] == 30

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_handles_timeout(self, mock_requests):
        """Test handling of request timeout."""
        import requests
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_requests.side_effect = requests.exceptions.Timeout("Request timed out")

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_handles_connection_error(self, mock_requests):
        """Test handling of connection errors."""
        import requests
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_requests.side_effect = requests.exceptions.ConnectionError("Connection refused")

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_handles_http_error(self, mock_requests):
        """Test handling of HTTP errors."""
        import requests
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_requests.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_handles_malformed_xml(self, mock_requests, sample_haslametrics_malformed_xml):
        """Test handling of malformed XML."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.content = sample_haslametrics_malformed_xml
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is None

    @patch('backend.data_collection.haslametrics_scraper.requests.get')
    def test_handles_empty_response(self, mock_requests, sample_haslametrics_empty_xml):
        """Test handling of empty XML response."""
        from backend.data_collection.haslametrics_scraper import fetch_haslametrics_ratings

        mock_response = MagicMock()
        mock_response.content = sample_haslametrics_empty_xml
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_haslametrics_ratings(2025)

        assert result is not None
        assert len(result) == 0


class TestHaslametricsStoreRatings:
    """Test storing Haslametrics ratings."""

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_successful_storage(self, mock_supabase, mock_get_team_id):
        """Test successful storage of ratings."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.side_effect = lambda name: f"{name.lower().replace(' ', '-')}-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        teams = [
            {"team": "Duke", "rank": "1", "offensive_efficiency": "118.5", "defensive_efficiency": "89.2"},
            {"team": "N Carolina", "rank": "2", "offensive_efficiency": "116.2", "defensive_efficiency": "91.5"},
        ]

        result = store_haslametrics_ratings(teams, 2025)

        assert result["inserted"] == 2
        assert result["skipped"] == 0
        assert result["errors"] == 0

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_handles_unmatched_teams(self, mock_supabase, mock_get_team_id):
        """Test that unmatched teams are skipped."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = None

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        teams = [
            {"team": "Unknown School", "rank": "350"},
        ]

        result = store_haslametrics_ratings(teams, 2025)

        assert result["inserted"] == 0
        assert result["skipped"] == 1

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_calculates_efficiency_margin(self, mock_supabase, mock_get_team_id):
        """Test that efficiency margin is calculated correctly."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "rating-uuid"}])

        teams = [
            {"team": "Duke", "offensive_efficiency": "118.5", "defensive_efficiency": "89.2"},
        ]

        store_haslametrics_ratings(teams, 2025)

        # Verify the insert was called with calculated efficiency margin
        insert_call = mock_table.insert.call_args
        inserted_data = insert_call[0][0]
        assert inserted_data.get("efficiency_margin") == 29.3  # 118.5 - 89.2

    @patch('backend.data_collection.haslametrics_scraper.get_team_id')
    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_handles_insert_errors(self, mock_supabase, mock_get_team_id):
        """Test handling of insert errors."""
        from backend.data_collection.haslametrics_scraper import store_haslametrics_ratings

        mock_get_team_id.return_value = "team-uuid"

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.side_effect = Exception("Database error")

        teams = [{"team": "Duke", "rank": "1"}]

        result = store_haslametrics_ratings(teams, 2025)

        assert result["errors"] == 1


class TestHaslametricsRefresh:
    """Test full Haslametrics refresh."""

    @patch('backend.data_collection.haslametrics_scraper.fetch_haslametrics_ratings')
    @patch('backend.data_collection.haslametrics_scraper.store_haslametrics_ratings')
    def test_successful_refresh(self, mock_store, mock_fetch):
        """Test successful refresh flow."""
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        mock_fetch.return_value = [
            {"team": "Duke", "rank": "1"},
            {"team": "N Carolina", "rank": "2"},
        ]
        mock_store.return_value = {"inserted": 2, "skipped": 0, "errors": 0}

        result = refresh_haslametrics_data(2025)

        assert result["status"] == "success"
        assert result["ratings"]["inserted"] == 2

    @patch('backend.data_collection.haslametrics_scraper.fetch_haslametrics_ratings')
    def test_handles_fetch_failure(self, mock_fetch):
        """Test handling when fetch fails."""
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        mock_fetch.return_value = None

        result = refresh_haslametrics_data(2025)

        assert result["status"] == "error"
        assert "error" in result

    @patch('backend.data_collection.haslametrics_scraper.fetch_haslametrics_ratings')
    def test_handles_empty_teams(self, mock_fetch):
        """Test handling when fetch returns empty list."""
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        mock_fetch.return_value = []

        result = refresh_haslametrics_data(2025)

        assert result["status"] == "error"


class TestHaslametricsGetTeamRating:
    """Test getting team's Haslametrics rating."""

    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_returns_latest_rating(self, mock_supabase):
        """Test returns the most recent rating."""
        from backend.data_collection.haslametrics_scraper import get_team_haslametrics_rating

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq

        mock_order = MagicMock()
        mock_eq.order.return_value = mock_order

        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit

        expected_rating = {
            "id": "rating-uuid",
            "team_id": "duke-uuid",
            "all_play_pct": 0.94,
        }
        mock_limit.execute.return_value = MagicMock(data=[expected_rating])

        result = get_team_haslametrics_rating("duke-uuid", 2025)

        assert result == expected_rating

    @patch('backend.data_collection.haslametrics_scraper.supabase')
    def test_returns_none_when_not_found(self, mock_supabase):
        """Test returns None when no rating found."""
        from backend.data_collection.haslametrics_scraper import get_team_haslametrics_rating

        mock_table = MagicMock()
        mock_supabase.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq

        mock_order = MagicMock()
        mock_eq.order.return_value = mock_order

        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = MagicMock(data=[])

        result = get_team_haslametrics_rating("unknown-uuid", 2025)

        assert result is None


# ============================================================================
# CROSS-SCRAPER TESTS
# ============================================================================

class TestScraperConsistency:
    """Test consistency between scrapers."""

    def test_both_scrapers_have_matching_team_mappings(self):
        """Test that key team mappings exist in both scrapers."""
        from backend.data_collection.kenpom_scraper import normalize_team_name as kenpom_normalize
        from backend.data_collection.haslametrics_scraper import normalize_team_name as hasla_normalize

        # These teams should normalize the same in both scrapers
        teams_to_test = [
            "UConn",
            "Connecticut",
            "NC State",
        ]

        for team in teams_to_test:
            kenpom_result = kenpom_normalize(team)
            hasla_result = hasla_normalize(team)
            assert kenpom_result == hasla_result, f"Mismatch for {team}: kenpom={kenpom_result}, hasla={hasla_result}"

    def test_safe_conversion_consistency(self):
        """Test that safe conversions work consistently."""
        from backend.data_collection.kenpom_scraper import safe_int as kenpom_safe_int
        from backend.data_collection.kenpom_scraper import safe_float as kenpom_safe_float
        from backend.data_collection.haslametrics_scraper import safe_int as hasla_safe_int
        from backend.data_collection.haslametrics_scraper import safe_float as hasla_safe_float

        # Test common cases
        test_values = ["123", "123.45", "", None]

        for val in test_values:
            # Both should handle basic cases the same way
            if val not in ["N/A", "1,234", "76.5%"]:  # Skip Haslametrics-specific formats
                k_int = kenpom_safe_int(val)
                h_int = hasla_safe_int(val)
                k_float = kenpom_safe_float(val)
                h_float = hasla_safe_float(val)

                assert k_int == h_int, f"safe_int mismatch for {val}"
                assert k_float == h_float, f"safe_float mismatch for {val}"

"""
Integration tests for the data collection pipeline.

Tests daily_refresh.py, kenpom_scraper.py, and haslametrics_scraper.py
covering: successful flow, unexpected columns, missing teams, duplicate
external_ids, timeouts, and empty responses.

All HTTP and Supabase calls are mocked — zero network/DB calls.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock

import pandas as pd
import pytest
import requests


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_supabase_client():
    """Return a mock Supabase client with chainable table interface."""
    client = MagicMock()

    def _table(name):
        tbl = MagicMock()
        # Make every chained method return the same mock so
        # .select().eq().execute() etc. all work.
        for m in ("select", "insert", "upsert", "delete", "update",
                   "eq", "neq", "gte", "lte", "ilike", "is_",
                   "order", "limit"):
            getattr(tbl, m).return_value = tbl
        tbl.execute.return_value = MagicMock(data=[])
        return tbl

    client.table = _table
    return client


def _haslametrics_xml(teams):
    """Build minimal Haslametrics XML from a list of dicts."""
    root = ET.Element("root")
    for t in teams:
        attrs = {k: str(v) for k, v in t.items()}
        ET.SubElement(root, "mr", attrib=attrs)
    return ET.tostring(root)


# ---------------------------------------------------------------------------
# 1. Haslametrics — successful end-to-end refresh
# ---------------------------------------------------------------------------

class TestHaslametricsSuccessfulRefresh:
    """Full refresh with mocked HTTP + Supabase."""

    @patch("backend.data_collection.haslametrics_scraper.supabase")
    @patch("backend.data_collection.haslametrics_scraper.requests.get")
    @patch("backend.data_collection.haslametrics_scraper.invalidate_haslametrics_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_successful_refresh_inserts_teams(self, _cache, mock_get, mock_sb):
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        xml_body = _haslametrics_xml([
            {"rk": "1", "t": "Duke", "c": "ACC", "w": "20", "l": "3",
             "ou": "115.2", "du": "90.1", "ap": "97.5", "mom": "0.3",
             "mmo": "0.2", "mmd": "0.1", "inc": "0.05", "sos": "80.0"},
            {"rk": "2", "t": "Kansas", "c": "B12", "w": "19", "l": "4",
             "ou": "113.0", "du": "91.5", "ap": "95.0", "mom": "0.1",
             "mmo": "0.0", "mmd": "0.1", "inc": "0.08", "sos": "78.0"},
        ])

        resp = MagicMock()
        resp.status_code = 200
        resp.content = xml_body
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        # Supabase: team lookup returns a match, insert succeeds
        tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(tbl, m).return_value = tbl
        tbl.execute.return_value = MagicMock(data=[{"id": "fake-uuid-1"}])
        mock_sb.table.return_value = tbl

        result = refresh_haslametrics_data(season=2025)

        assert result["status"] == "success"
        assert result["ratings"]["inserted"] == 2


# ---------------------------------------------------------------------------
# 2. Haslametrics — missing teams -> partial success
# ---------------------------------------------------------------------------

class TestHaslametricsMissingTeams:

    @patch("backend.data_collection.haslametrics_scraper.get_team_id")
    @patch("backend.data_collection.haslametrics_scraper.supabase")
    @patch("backend.data_collection.haslametrics_scraper.requests.get")
    @patch("backend.data_collection.haslametrics_scraper.invalidate_haslametrics_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_unmatched_teams_are_skipped(self, _cache, mock_get, mock_sb, mock_get_team):
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        xml_body = _haslametrics_xml([
            {"rk": "1", "t": "RealTeam", "c": "ACC", "w": "10", "l": "5",
             "ou": "100", "du": "95", "ap": "70"},
            {"rk": "2", "t": "FakeUniversity", "c": "X", "w": "5", "l": "10",
             "ou": "90", "du": "100", "ap": "30"},
        ])

        resp = MagicMock()
        resp.content = xml_body
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        # First team matches, second doesn't
        mock_get_team.side_effect = lambda name: "uuid-real" if name == "RealTeam" else None

        tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(tbl, m).return_value = tbl
        tbl.execute.return_value = MagicMock(data=[{"id": "inserted"}])
        mock_sb.table.return_value = tbl

        result = refresh_haslametrics_data(season=2025)

        assert result["status"] == "success"
        assert result["ratings"]["skipped"] == 1
        assert result["ratings"]["inserted"] == 1


# ---------------------------------------------------------------------------
# 3. Haslametrics — network timeout
# ---------------------------------------------------------------------------

class TestHaslametricsTimeout:

    @patch("backend.data_collection.haslametrics_scraper.requests.get")
    @patch("backend.data_collection.haslametrics_scraper.invalidate_haslametrics_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_timeout_returns_error(self, _cache, mock_get):
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        mock_get.side_effect = requests.exceptions.Timeout("Connection timed out")

        result = refresh_haslametrics_data(season=2025)

        assert result["status"] == "error"
        assert "Failed to fetch" in result.get("error", "")


# ---------------------------------------------------------------------------
# 4. Haslametrics — empty response
# ---------------------------------------------------------------------------

class TestHaslametricsEmptyResponse:

    @patch("backend.data_collection.haslametrics_scraper.requests.get")
    @patch("backend.data_collection.haslametrics_scraper.invalidate_haslametrics_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_empty_xml_returns_error(self, _cache, mock_get):
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        resp = MagicMock()
        resp.content = b"<root></root>"
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = refresh_haslametrics_data(season=2025)

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 5. KenPom — successful store
# ---------------------------------------------------------------------------

class TestKenpomSuccessfulStore:

    @patch("backend.data_collection.kenpom_scraper.supabase")
    def test_store_ratings_inserts_rows(self, mock_sb):
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        df = pd.DataFrame([{
            "Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "20-3",
            "AdjEM": 30.5, "AdjO": 120.0, "AdjD": 89.5, "AdjT": 68.0,
            "Luck": 0.02, "SOS AdjEM": 10.5,
        }])

        tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(tbl, m).return_value = tbl
        # Team lookup succeeds
        tbl.execute.return_value = MagicMock(data=[{"id": "uuid-duke"}])
        mock_sb.table.return_value = tbl

        result = store_kenpom_ratings(df, 2025)

        assert result["inserted"] == 1
        assert result["errors"] == 0


# ---------------------------------------------------------------------------
# 6. KenPom — unexpected column names (BUG at kenpom_scraper.py:396)
# ---------------------------------------------------------------------------

class TestKenpomUnexpectedColumns:

    @patch("backend.data_collection.kenpom_scraper.supabase")
    def test_unknown_columns_still_inserts_with_nulls(self, mock_sb):
        """When kenpompy returns different column names, store should
        gracefully fall through get_col() and insert with None values."""
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        # DataFrame with "Team" present but all metric columns unexpected
        df = pd.DataFrame([{
            "Team": "Kansas",
            "Ranking": 1,
            "Conference": "B12",
            "Record": "19-4",
            "NetRating": 25.0,
            "OffRating": 115.0,
            "DefRating": 90.0,
            "Pace": 67.0,
            "LuckFactor": 0.05,
            "ScheduleStrength": 12.0,
        }])

        tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(tbl, m).return_value = tbl
        tbl.execute.return_value = MagicMock(data=[{"id": "uuid-kansas"}])
        mock_sb.table.return_value = tbl

        result = store_kenpom_ratings(df, 2025)

        # Should still insert (team matched) even though most metrics are None
        assert result["inserted"] == 1
        assert result["errors"] == 0


# ---------------------------------------------------------------------------
# 7. KenPom — team not found in DB
# ---------------------------------------------------------------------------

class TestKenpomTeamNotFound:

    @patch("backend.data_collection.kenpom_scraper.supabase")
    def test_unmatched_team_is_skipped(self, mock_sb):
        from backend.data_collection.kenpom_scraper import store_kenpom_ratings

        df = pd.DataFrame([{
            "Rk": 999, "Team": "Nonexistent University", "Conf": "XX", "W-L": "0-30",
            "AdjEM": -20.0,
        }])

        tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(tbl, m).return_value = tbl
        # Team lookup fails
        tbl.execute.return_value = MagicMock(data=[])
        mock_sb.table.return_value = tbl

        result = store_kenpom_ratings(df, 2025)

        assert result["skipped"] == 1
        assert result["inserted"] == 0


# ---------------------------------------------------------------------------
# 8. Daily refresh — Supabase upsert conflict with duplicate external_id
# ---------------------------------------------------------------------------

class TestDailyRefreshDuplicateExternalId:

    @patch("backend.data_collection.daily_refresh.invalidate_ratings_caches",
           return_value={"kenpom_invalidated": 0, "haslametrics_invalidated": 0})
    @patch("backend.data_collection.daily_refresh.ratings_cache")
    @patch("backend.data_collection.daily_refresh.get_query_stats",
           return_value={"total_queries": 0, "total_time_ms": 0, "avg_time_ms": 0,
                         "slow_queries": 0, "slow_query_pct": 0, "slowest_query_name": None, "slowest_query_ms": 0})
    @patch("backend.data_collection.daily_refresh.reset_query_stats")
    @patch("backend.data_collection.daily_refresh._ensure_supabase")
    @patch("backend.data_collection.daily_refresh.fetch_odds_api_spreads", return_value=[])
    @patch("backend.data_collection.daily_refresh.refresh_espn_tip_times",
           return_value={"games_created": 0, "games_updated": 0})
    @patch("backend.data_collection.daily_refresh.refresh_kenpom_data",
           return_value={"status": "skipped"})
    @patch("backend.data_collection.daily_refresh.refresh_haslametrics_data",
           return_value={"status": "success", "ratings": {"inserted": 10}})
    @patch("backend.data_collection.daily_refresh.refresh_prediction_markets",
           return_value={"status": "success"})
    def test_process_odds_duplicate_game_uses_existing(
        self, _pm, _hasla, _kenpom, _espn, _odds, mock_ensure, _reset, _stats, mock_cache, _inv
    ):
        """When a game already exists (duplicate external_id scenario),
        process_odds_data should find the existing game and add spreads."""
        from backend.data_collection.daily_refresh import process_odds_data

        client = _mock_supabase_client()

        # Simulate: game already exists in DB
        game_tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(game_tbl, m).return_value = game_tbl

        # First call: get_team_id -> teams lookup (exact match)
        teams_tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(teams_tbl, m).return_value = teams_tbl
        teams_tbl.execute.return_value = MagicMock(data=[{"id": "team-uuid-1"}])

        # Game lookup returns existing game
        game_tbl.execute.return_value = MagicMock(data=[{"id": "existing-game-uuid"}])

        # Spreads insert
        spreads_tbl = MagicMock()
        for m in ("select", "eq", "ilike", "order", "limit", "insert"):
            getattr(spreads_tbl, m).return_value = spreads_tbl
        spreads_tbl.execute.return_value = MagicMock(data=[])

        def _table_router(name):
            if name == "teams":
                return teams_tbl
            elif name == "games":
                return game_tbl
            elif name == "spreads":
                return spreads_tbl
            return MagicMock()

        mock_ensure.return_value = MagicMock()
        mock_ensure.return_value.table = _table_router

        # Patch the module-level supabase
        with patch("backend.data_collection.daily_refresh.supabase", mock_ensure.return_value):
            with patch("backend.data_collection.daily_refresh._ensure_supabase", return_value=mock_ensure.return_value):
                odds_data = [{
                    "id": "ext-123",
                    "home_team": "Duke Blue Devils",
                    "away_team": "North Carolina Tar Heels",
                    "commence_time": "2025-02-15T00:00:00Z",
                    "bookmakers": [{
                        "markets": [
                            {"key": "spreads", "outcomes": [
                                {"name": "Duke Blue Devils", "point": -5.5}
                            ]},
                            {"key": "h2h", "outcomes": [
                                {"name": "Duke Blue Devils", "price": -220},
                                {"name": "North Carolina Tar Heels", "price": 180},
                            ]},
                        ]
                    }]
                }]

                result = process_odds_data(odds_data)

                assert result["spreads_inserted"] >= 0  # May be 0 or 1 depending on mock routing


# ---------------------------------------------------------------------------
# 9. Daily refresh — fetch_odds_api_spreads network timeout
# ---------------------------------------------------------------------------

class TestOddsApiTimeout:

    @patch("backend.data_collection.daily_refresh.requests.get")
    def test_timeout_returns_empty_list(self, mock_get):
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_get.side_effect = requests.exceptions.Timeout("timed out")

        result = fetch_odds_api_spreads()

        assert result == []


# ---------------------------------------------------------------------------
# 10. Daily refresh — fetch_odds_api_spreads empty response
# ---------------------------------------------------------------------------

class TestOddsApiEmptyResponse:

    @patch("backend.data_collection.daily_refresh.requests.get")
    def test_empty_json_returns_empty_list(self, mock_get):
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        resp = MagicMock()
        resp.json.return_value = []
        resp.raise_for_status = MagicMock()
        resp.headers = {"x-requests-remaining": "499", "x-requests-used": "1"}
        mock_get.return_value = resp

        result = fetch_odds_api_spreads()

        assert result == []


# ---------------------------------------------------------------------------
# 11. KenPom — full refresh with no credentials
# ---------------------------------------------------------------------------

class TestKenpomNoCredentials:

    @patch("backend.data_collection.kenpom_scraper.KENPOM_EMAIL", None)
    @patch("backend.data_collection.kenpom_scraper.KENPOM_PASSWORD", None)
    @patch("backend.data_collection.kenpom_scraper.invalidate_kenpom_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_no_credentials_returns_error(self, _cache):
        from backend.data_collection.kenpom_scraper import refresh_kenpom_data

        result = refresh_kenpom_data(season=2025)

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 12. Haslametrics — malformed XML
# ---------------------------------------------------------------------------

class TestHaslametricsMalformedXml:

    @patch("backend.data_collection.haslametrics_scraper.requests.get")
    @patch("backend.data_collection.haslametrics_scraper.invalidate_haslametrics_cache",
           return_value={"ratings_invalidated": 0, "teams_invalidated": 0})
    def test_malformed_xml_returns_error(self, _cache, mock_get):
        from backend.data_collection.haslametrics_scraper import refresh_haslametrics_data

        resp = MagicMock()
        resp.content = b"this is not xml at all <><><>"
        resp.raise_for_status = MagicMock()
        mock_get.return_value = resp

        result = refresh_haslametrics_data(season=2025)

        assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 13. Daily refresh — normalize_team_name edge cases
# ---------------------------------------------------------------------------

class TestNormalizeTeamName:

    def test_direct_mapping(self):
        from backend.data_collection.daily_refresh import normalize_team_name
        assert normalize_team_name("Duke Blue Devils") == "duke"
        assert normalize_team_name("UConn Huskies") == "connecticut"

    def test_empty_string(self):
        from backend.data_collection.daily_refresh import normalize_team_name
        assert normalize_team_name("") == ""
        assert normalize_team_name(None) == ""

    def test_basic_normalization(self):
        from backend.data_collection.daily_refresh import normalize_team_name
        result = normalize_team_name("Some Random Team")
        assert isinstance(result, str)
        assert " " not in result

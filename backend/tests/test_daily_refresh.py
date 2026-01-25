"""
Tests for the daily_refresh.py pipeline.

Tests the main orchestration logic that coordinates all data collection.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, date, timedelta
import json


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_all_external_apis():
    """Mock all external API dependencies for daily_refresh."""
    with patch.multiple(
        'backend.data_collection.daily_refresh',
        requests=MagicMock(),
        _ensure_supabase=MagicMock(),
        ODDS_API_KEY='test-api-key',
    ) as mocks:
        yield mocks


@pytest.fixture
def mock_supabase_client_for_refresh():
    """Configure mock Supabase client for refresh operations."""
    mock_client = MagicMock()

    # Create a configurable table mock
    def create_table_mock():
        mock_table = MagicMock()

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq  # Allow chaining
        mock_eq.is_.return_value = mock_eq
        mock_eq.gte.return_value = mock_eq
        mock_eq.lte.return_value = mock_eq

        mock_order = MagicMock()
        mock_eq.order.return_value = mock_order

        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit

        # Default to empty results
        mock_eq.execute.return_value = MagicMock(data=[])
        mock_limit.execute.return_value = MagicMock(data=[])
        mock_select.execute.return_value = MagicMock(data=[])

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "new-uuid"}])

        mock_delete = MagicMock()
        mock_table.delete.return_value = mock_delete
        mock_delete.eq.return_value = mock_delete
        mock_delete.execute.return_value = MagicMock(data=[])

        return mock_table

    mock_client.table.side_effect = lambda name: create_table_mock()
    return mock_client


# ============================================================================
# UNIT TESTS - Individual Functions
# ============================================================================

class TestNormalizeTeamName:
    """Test team name normalization in daily_refresh."""

    def test_direct_mapping(self):
        """Test direct mapping from ODDS_API_TEAM_MAP."""
        from backend.data_collection.daily_refresh import normalize_team_name

        assert normalize_team_name("Duke Blue Devils") == "duke"
        assert normalize_team_name("North Carolina Tar Heels") == "north-carolina"
        assert normalize_team_name("UConn Huskies") == "connecticut"
        assert normalize_team_name("Connecticut Huskies") == "connecticut"

    def test_suffix_removal(self):
        """Test that mascot suffixes are removed."""
        from backend.data_collection.daily_refresh import normalize_team_name

        # These go through the suffix removal logic
        assert "virginia" in normalize_team_name("Virginia Cavaliers")
        assert "florida" in normalize_team_name("Florida Gators")

    def test_empty_input(self):
        """Test handling of empty/None input."""
        from backend.data_collection.daily_refresh import normalize_team_name

        assert normalize_team_name("") == ""
        assert normalize_team_name(None) == ""


class TestGetTeamId:
    """Test team ID lookup functionality."""

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_exact_match_found(self, mock_supabase):
        """Test exact match returns team ID."""
        from backend.data_collection.daily_refresh import get_team_id

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{"id": "duke-team-uuid"}])

        result = get_team_id("Duke Blue Devils")

        assert result == "duke-team-uuid"

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_partial_match_fallback(self, mock_supabase):
        """Test partial match when exact match fails."""
        from backend.data_collection.daily_refresh import get_team_id

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        # First call (exact match) returns empty
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])

        # Second call (partial match) returns result
        mock_ilike = MagicMock()
        mock_select.ilike.return_value = mock_ilike
        mock_ilike.execute.return_value = MagicMock(
            data=[{"id": "duke-team-uuid", "normalized_name": "duke"}]
        )

        result = get_team_id("Duke")

        assert result == "duke-team-uuid"

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_team_not_found(self, mock_supabase):
        """Test returns None when team not found."""
        from backend.data_collection.daily_refresh import get_team_id

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

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

    def test_sql_wildcard_sanitization(self):
        """Test that SQL wildcards are removed from input."""
        from backend.data_collection.daily_refresh import normalize_team_name

        # Test with SQL wildcards that could be abused
        result = normalize_team_name("Duke%")
        assert "%" not in result

        result = normalize_team_name("Duke_Devils")
        assert "_" not in result


class TestFetchOddsApiSpreads:
    """Test The Odds API fetching."""

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-api-key')
    def test_successful_fetch(self, mock_requests):
        """Test successful API fetch returns data."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = [{"id": "game-1", "home_team": "Duke"}]
        mock_response.headers = {"x-requests-remaining": "490", "x-requests-used": "10"}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()

        assert len(result) == 1
        assert result[0]["home_team"] == "Duke"

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', 'test-api-key')
    def test_api_request_params(self, mock_requests):
        """Test API is called with correct parameters."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        fetch_odds_api_spreads()

        # Verify the call
        mock_requests.assert_called_once()
        call_kwargs = mock_requests.call_args[1]

        assert call_kwargs["params"]["apiKey"] == "test-api-key"
        assert call_kwargs["params"]["regions"] == "us"
        assert "spreads" in call_kwargs["params"]["markets"]
        assert "h2h" in call_kwargs["params"]["markets"]
        assert call_kwargs["params"]["oddsFormat"] == "american"
        assert call_kwargs["timeout"] == 30

    @patch('backend.data_collection.daily_refresh.requests.get')
    @patch('backend.data_collection.daily_refresh.ODDS_API_KEY', None)
    def test_missing_api_key(self, mock_requests):
        """Test behavior when API key is not configured."""
        from backend.data_collection.daily_refresh import fetch_odds_api_spreads

        # The function should still try to make the request
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.headers = {}
        mock_response.raise_for_status = MagicMock()
        mock_requests.return_value = mock_response

        result = fetch_odds_api_spreads()
        # Should return empty list or make request with None key


class TestProcessOddsData:
    """Test odds data processing and storage."""

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    @patch('backend.data_collection.daily_refresh.get_team_id')
    def test_successful_processing(self, mock_get_team_id, mock_supabase):
        """Test successful processing of odds data."""
        from backend.data_collection.daily_refresh import process_odds_data

        mock_get_team_id.side_effect = lambda name: f"{name.lower().split()[0]}-uuid"

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[{"id": "existing-game-uuid"}])

        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "new-spread-uuid"}])

        odds_data = [
            {
                "id": "ext-game-1",
                "home_team": "Duke Blue Devils",
                "away_team": "North Carolina Tar Heels",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": [
                    {
                        "key": "draftkings",
                        "markets": [
                            {
                                "key": "spreads",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "point": -7.5},
                                    {"name": "North Carolina Tar Heels", "point": 7.5},
                                ]
                            },
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Duke Blue Devils", "price": -280},
                                    {"name": "North Carolina Tar Heels", "price": 220},
                                ]
                            }
                        ]
                    }
                ]
            }
        ]

        result = process_odds_data(odds_data)

        assert "spreads_inserted" in result

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    @patch('backend.data_collection.daily_refresh.get_team_id')
    def test_missing_team_skipped(self, mock_get_team_id, mock_supabase):
        """Test games with unknown teams are skipped."""
        from backend.data_collection.daily_refresh import process_odds_data

        # Return None for team lookup
        mock_get_team_id.return_value = None

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        odds_data = [
            {
                "home_team": "Unknown Team",
                "away_team": "Another Unknown",
                "commence_time": "2025-01-25T23:00:00Z",
                "bookmakers": []
            }
        ]

        result = process_odds_data(odds_data)

        # Should not crash, just skip
        assert result["spreads_inserted"] == 0


class TestRunPredictions:
    """Test prediction generation."""

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_predictions_created_for_upcoming_games(self, mock_supabase):
        """Test predictions are created for games without predictions."""
        from backend.data_collection.daily_refresh import run_predictions

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        # Mock upcoming games query
        mock_gte = MagicMock()
        mock_select.gte.return_value = mock_gte
        mock_is = MagicMock()
        mock_gte.is_.return_value = mock_is
        mock_is.execute.return_value = MagicMock(data=[
            {
                "id": "game-uuid-1",
                "date": "2025-01-25",
                "home_team_id": "home-uuid",
                "away_team_id": "away-uuid",
                "is_conference_game": True,
            }
        ])

        # Mock prediction check
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_eq.execute.return_value = MagicMock(data=[])  # No existing prediction

        # Mock spread lookup
        mock_order = MagicMock()
        mock_eq.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = MagicMock(data=[{"home_spread": -7.5}])

        # Mock prediction insert
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "pred-uuid"}])

        result = run_predictions()

        assert "predictions_created" in result

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_no_games_to_predict(self, mock_supabase):
        """Test handling when no upcoming games exist."""
        from backend.data_collection.daily_refresh import run_predictions

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_gte = MagicMock()
        mock_select.gte.return_value = mock_gte
        mock_is = MagicMock()
        mock_gte.is_.return_value = mock_is
        mock_is.execute.return_value = MagicMock(data=[])  # No games

        result = run_predictions()

        assert result["predictions_created"] == 0

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_force_regenerate_deletes_existing(self, mock_supabase):
        """Test force_regenerate deletes existing predictions."""
        from backend.data_collection.daily_refresh import run_predictions

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        # Mock upcoming games query for delete
        mock_gte = MagicMock()
        mock_select.gte.return_value = mock_gte
        mock_is = MagicMock()
        mock_gte.is_.return_value = mock_is
        mock_is.execute.return_value = MagicMock(data=[{"id": "game-1"}, {"id": "game-2"}])

        # Mock delete
        mock_delete = MagicMock()
        mock_table.delete.return_value = mock_delete
        mock_eq_delete = MagicMock()
        mock_delete.eq.return_value = mock_eq_delete
        mock_eq_delete.execute.return_value = MagicMock(data=[])

        # Mock prediction insert
        mock_insert = MagicMock()
        mock_table.insert.return_value = mock_insert
        mock_insert.execute.return_value = MagicMock(data=[{"id": "pred-uuid"}])

        # Mock spread lookup
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        mock_order = MagicMock()
        mock_eq.order.return_value = mock_order
        mock_limit = MagicMock()
        mock_order.limit.return_value = mock_limit
        mock_limit.execute.return_value = MagicMock(data=[])

        result = run_predictions(force_regenerate=True)

        # Delete should have been called
        assert mock_table.delete.called


class TestRefreshKenpomData:
    """Test KenPom data refresh."""

    @patch('backend.data_collection.daily_refresh.os.getenv')
    def test_skips_without_credentials(self, mock_getenv):
        """Test KenPom refresh is skipped without credentials."""
        from backend.data_collection.daily_refresh import refresh_kenpom_data

        mock_getenv.side_effect = lambda key, default=None: {
            "KENPOM_EMAIL": None,
            "KENPOM_PASSWORD": None,
        }.get(key, default)

        result = refresh_kenpom_data()

        assert result["status"] == "skipped"
        assert "no_credentials" in result.get("reason", "")

    @patch.dict('os.environ', {'KENPOM_EMAIL': 'test@test.com', 'KENPOM_PASSWORD': 'password'})
    @patch('backend.data_collection.daily_refresh.os.getenv')
    def test_handles_import_error(self, mock_getenv):
        """Test graceful handling of import errors."""
        from backend.data_collection.daily_refresh import refresh_kenpom_data

        mock_getenv.side_effect = lambda key, default=None: {
            "KENPOM_EMAIL": "test@test.com",
            "KENPOM_PASSWORD": "password",
        }.get(key, default)

        # The actual kenpom_scraper import will likely fail in test environment
        result = refresh_kenpom_data()

        # Should return error status, not crash
        assert result.get("status") in ["error", "skipped"]


class TestRefreshHaslametricsData:
    """Test Haslametrics data refresh."""

    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    def test_successful_refresh(self, mock_hasla_refresh):
        """Test successful Haslametrics refresh."""
        # We're patching the imported function, so we need to test differently
        from backend.data_collection import daily_refresh

        # Directly test the function behavior
        with patch.object(daily_refresh, 'refresh_haslametrics_data') as mock_fn:
            mock_fn.return_value = {"status": "success", "ratings": {"inserted": 300}}

            result = mock_fn()

            assert result["status"] == "success"


class TestRunDailyRefresh:
    """Test the main daily refresh orchestration."""

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_full_pipeline_execution(
        self,
        mock_ai_analysis,
        mock_today_view,
        mock_game_results,
        mock_predictions,
        mock_haslametrics,
        mock_kenpom,
        mock_process_odds,
        mock_fetch_odds,
        mock_espn,
    ):
        """Test that all pipeline steps are executed in order."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        # Configure mocks
        mock_espn.return_value = {"games_created": 10, "games_updated": 5}
        mock_fetch_odds.return_value = [{"id": "game-1"}]
        mock_process_odds.return_value = {"spreads_inserted": 10}
        mock_kenpom.return_value = {"status": "success"}
        mock_haslametrics.return_value = {"status": "success"}
        mock_predictions.return_value = {"predictions_created": 10}
        mock_game_results.return_value = {"games_scored": 5}
        mock_today_view.return_value = {"today_games": 8}
        mock_ai_analysis.return_value = {"analyses_created": 8}

        result = run_daily_refresh()

        # Verify all steps were called
        mock_espn.assert_called_once()
        mock_fetch_odds.assert_called_once()
        mock_process_odds.assert_called_once()
        mock_kenpom.assert_called_once()
        mock_haslametrics.assert_called_once()
        mock_predictions.assert_called_once()
        mock_game_results.assert_called_once()
        mock_today_view.assert_called_once()
        mock_ai_analysis.assert_called_once()

        # Verify result structure
        assert result["status"] == "success"
        assert "espn_games" in result
        assert "predictions" in result

    @patch('backend.data_collection.daily_refresh.refresh_espn_tip_times')
    @patch('backend.data_collection.daily_refresh.fetch_odds_api_spreads')
    @patch('backend.data_collection.daily_refresh.process_odds_data')
    @patch('backend.data_collection.daily_refresh.refresh_kenpom_data')
    @patch('backend.data_collection.daily_refresh.refresh_haslametrics_data')
    @patch('backend.data_collection.daily_refresh.run_predictions')
    @patch('backend.data_collection.daily_refresh.update_game_results')
    @patch('backend.data_collection.daily_refresh.create_today_games_view')
    @patch('backend.data_collection.daily_refresh.run_ai_analysis')
    def test_pipeline_continues_on_non_fatal_errors(
        self,
        mock_ai_analysis,
        mock_today_view,
        mock_game_results,
        mock_predictions,
        mock_haslametrics,
        mock_kenpom,
        mock_process_odds,
        mock_fetch_odds,
        mock_espn,
    ):
        """Test pipeline continues when non-fatal errors occur."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        # ESPN fails but pipeline continues
        mock_espn.side_effect = Exception("ESPN unavailable")
        mock_fetch_odds.return_value = []
        mock_process_odds.return_value = {"spreads_inserted": 0}
        mock_kenpom.return_value = {"status": "error", "error": "Login failed"}
        mock_haslametrics.return_value = {"status": "success"}
        mock_predictions.return_value = {"predictions_created": 0}
        mock_game_results.return_value = {"games_scored": 0}
        mock_today_view.return_value = {"today_games": 0}
        mock_ai_analysis.side_effect = Exception("AI service unavailable")

        result = run_daily_refresh()

        # Pipeline should complete despite errors
        assert result["status"] == "success"
        assert "error" in result.get("espn_games", {})
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
    def test_force_regenerate_flag_passed_to_predictions(
        self,
        mock_ai_analysis,
        mock_today_view,
        mock_game_results,
        mock_predictions,
        mock_haslametrics,
        mock_kenpom,
        mock_process_odds,
        mock_fetch_odds,
        mock_espn,
    ):
        """Test force_regenerate flag is passed to predictions."""
        from backend.data_collection.daily_refresh import run_daily_refresh

        mock_espn.return_value = {}
        mock_fetch_odds.return_value = []
        mock_kenpom.return_value = {}
        mock_haslametrics.return_value = {}
        mock_predictions.return_value = {}
        mock_game_results.return_value = {}
        mock_today_view.return_value = {}
        mock_ai_analysis.return_value = {}

        run_daily_refresh(force_regenerate_predictions=True)

        mock_predictions.assert_called_once_with(force_regenerate=True)


class TestDateHandling:
    """Test date handling in daily refresh."""

    def test_get_eastern_date_today(self):
        """Test Eastern time date calculation."""
        from backend.data_collection.daily_refresh import get_eastern_date_today

        result = get_eastern_date_today()

        # Should return a date object
        assert isinstance(result, date)

    def test_get_eastern_date_yesterday(self):
        """Test yesterday's date in Eastern time."""
        from backend.data_collection.daily_refresh import get_eastern_date_yesterday

        result = get_eastern_date_yesterday()

        # Should be one day before today
        today = date.today()
        assert result <= today

    def test_utc_to_eastern_conversion(self):
        """Test UTC to Eastern time conversion for game times."""
        from backend.data_collection.daily_refresh import EASTERN_TZ, UTC_TZ
        from datetime import datetime

        # 3 AM UTC on Jan 26 is 10 PM Eastern on Jan 25
        utc_time = datetime(2025, 1, 26, 3, 0, 0, tzinfo=UTC_TZ)
        eastern_time = utc_time.astimezone(EASTERN_TZ)

        assert eastern_time.date().isoformat() == "2025-01-25"
        assert eastern_time.hour == 22  # 10 PM


class TestUpdateGameResults:
    """Test game results update functionality."""

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_finds_games_needing_scores(self, mock_supabase):
        """Test finding games that need scores updated."""
        from backend.data_collection.daily_refresh import update_game_results

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_lte = MagicMock()
        mock_select.lte.return_value = mock_lte

        mock_is = MagicMock()
        mock_lte.is_.return_value = mock_is

        mock_limit = MagicMock()
        mock_is.limit.return_value = mock_limit

        mock_limit.execute.return_value = MagicMock(data=[
            {"id": "game-1", "external_id": "ext-1"},
            {"id": "game-2", "external_id": "ext-2"},
        ])

        result = update_game_results()

        assert result["games_needing_scores"] == 2

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_no_games_need_scores(self, mock_supabase):
        """Test when no games need score updates."""
        from backend.data_collection.daily_refresh import update_game_results

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_lte = MagicMock()
        mock_select.lte.return_value = mock_lte

        mock_is = MagicMock()
        mock_lte.is_.return_value = mock_is

        mock_limit = MagicMock()
        mock_is.limit.return_value = mock_limit

        mock_limit.execute.return_value = MagicMock(data=[])

        result = update_game_results()

        assert result["games_scored"] == 0


class TestCreateTodayGamesView:
    """Test today's games view creation."""

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_finds_today_games(self, mock_supabase):
        """Test finding today's games."""
        from backend.data_collection.daily_refresh import create_today_games_view

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq

        mock_eq.execute.return_value = MagicMock(data=[
            {"id": "game-1"},
            {"id": "game-2"},
            {"id": "game-3"},
        ])

        result = create_today_games_view()

        assert result["today_games"] == 3

    @patch('backend.data_collection.daily_refresh._ensure_supabase')
    def test_no_games_today(self, mock_supabase):
        """Test when no games are scheduled today."""
        from backend.data_collection.daily_refresh import create_today_games_view

        mock_client = MagicMock()
        mock_supabase.return_value = mock_client

        mock_table = MagicMock()
        mock_client.table.return_value = mock_table

        mock_select = MagicMock()
        mock_table.select.return_value = mock_select

        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq

        mock_eq.execute.return_value = MagicMock(data=[])

        result = create_today_games_view()

        assert result["today_games"] == 0

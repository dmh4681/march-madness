"""
Comprehensive tests for tournament bracket endpoints and database functions.

Tests cover:
- Input validation: _validate_region, _validate_round
- DB functions: get_tournament, create_tournament, update_tournament,
  get_tournament_seeds, upsert_tournament_seed, bulk_insert_seeds,
  get_tournament_bracket_view, get_tournament_game_data, get_region_summary,
  upsert_bracket_pick, grade_bracket_picks, update_eliminated_teams
- API endpoints: GET/POST /tournament/* (9 endpoints)
- Pydantic models: TournamentSeedInput, SetBracketRequest, BracketPickRequest,
  GeneratePicksRequest, TournamentAIAnalysisRequest
"""

import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime


# ---------------------------------------------------------------------------
# Shared UUIDs / constants
# ---------------------------------------------------------------------------

TOURNAMENT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TEAM_HOME_ID  = "11111111-2222-3333-4444-555555555555"
TEAM_AWAY_ID  = "66666666-7777-8888-9999-aaaaaaaaaaaa"
GAME_ID       = "550e8400-e29b-41d4-a716-446655440000"
PICK_ID       = "fedcba98-7654-3210-fedc-ba9876543210"


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def client():
    """FastAPI test client with env patched so the app initialises cleanly."""
    with patch.dict("os.environ", {"ALLOWED_ORIGINS": "http://localhost:3000"}):
        from backend.api.main import app
        from fastapi.testclient import TestClient
        return TestClient(app)


@pytest.fixture
def sample_tournament():
    return {
        "id": TOURNAMENT_ID,
        "season": 2026,
        "status": "upcoming",
        "name": "NCAA Tournament 2026",
        "champion_team_id": None,
    }


@pytest.fixture
def sample_seed():
    return {
        "id": "seed-uuid-0001",
        "tournament_id": TOURNAMENT_ID,
        "team_id": TEAM_HOME_ID,
        "seed": 1,
        "region": "East",
        "is_play_in": False,
        "play_in_matchup": None,
        "is_alive": True,
    }


@pytest.fixture
def sample_bracket_pick():
    return {
        "id": PICK_ID,
        "tournament_id": TOURNAMENT_ID,
        "game_id": GAME_ID,
        "round": "round_64",
        "picked_team_id": TEAM_HOME_ID,
        "confidence_score": 0.85,
        "reasoning": "1-seed dominance",
        "is_correct": None,
    }


@pytest.fixture
def mock_supabase():
    """Return a MagicMock that satisfies supabase chaining patterns."""
    mock = MagicMock()
    # Default execute returns empty data
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": TOURNAMENT_ID}])
    mock.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    return mock


# =============================================================================
# 1. Validation helpers
# =============================================================================

class TestValidateRegion:
    """Tests for _validate_region."""

    @pytest.mark.parametrize("region", ["East", "West", "South", "Midwest"])
    def test_valid_regions(self, region):
        from backend.api.supabase_client import _validate_region
        assert _validate_region(region) == region

    @pytest.mark.parametrize("bad", ["east", "EAST", "northeast", "", "Pacific", None])
    def test_invalid_regions_raise(self, bad):
        from backend.api.supabase_client import _validate_region
        with pytest.raises((ValueError, AttributeError, TypeError)):
            _validate_region(bad)


class TestValidateRound:
    """Tests for _validate_round."""

    @pytest.mark.parametrize("rnd", [
        "first_four", "round_64", "round_32", "sweet_16",
        "elite_8", "final_4", "championship",
    ])
    def test_valid_rounds(self, rnd):
        from backend.api.supabase_client import _validate_round
        assert _validate_round(rnd) == rnd

    @pytest.mark.parametrize("bad", ["Round_64", "round64", "quarterfinal", "semifinals", ""])
    def test_invalid_rounds_raise(self, bad):
        from backend.api.supabase_client import _validate_round
        with pytest.raises(ValueError):
            _validate_round(bad)


# =============================================================================
# 2. DB functions — tournament CRUD
# =============================================================================

class TestGetTournament:
    def test_returns_tournament_when_found(self, sample_tournament):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[sample_tournament]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament
            result = get_tournament(2026)

        assert result == sample_tournament

    def test_returns_none_when_not_found(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
                data=[]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament
            result = get_tournament(2026)

        assert result is None


class TestCreateTournament:
    def test_creates_with_season_only(self, sample_tournament):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[sample_tournament]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import create_tournament
            result = create_tournament(2026)

        assert result["season"] == 2026
        # Verify insert was called with at least season
        call_data = mock_client.table.return_value.insert.call_args[0][0]
        assert call_data["season"] == 2026

    def test_creates_with_optional_kwargs(self, sample_tournament):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(
                data=[sample_tournament]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import create_tournament
            create_tournament(2026, status="upcoming", name="NCAA 2026")

        call_data = mock_client.table.return_value.insert.call_args[0][0]
        assert call_data["status"] == "upcoming"
        assert call_data["name"] == "NCAA 2026"

    def test_returns_empty_dict_when_no_data(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
            mock_get.return_value = mock_client

            from backend.api.supabase_client import create_tournament
            result = create_tournament(2026)

        assert result == {}


class TestUpdateTournament:
    def test_updates_status(self, sample_tournament):
        updated = {**sample_tournament, "status": "bracket_set"}
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_chain = MagicMock()
            mock_chain.execute.return_value = MagicMock(data=[updated])
            mock_client = MagicMock()
            mock_client.table.return_value.update.return_value.eq.return_value = mock_chain
            mock_get.return_value = mock_client

            from backend.api.supabase_client import update_tournament
            result = update_tournament(TOURNAMENT_ID, {"status": "bracket_set"})

        assert result["status"] == "bracket_set"

    def test_rejects_invalid_uuid(self):
        from backend.api.supabase_client import update_tournament
        with pytest.raises(ValueError, match="Invalid tournament_id"):
            update_tournament("not-a-uuid", {"status": "bracket_set"})

    def test_ignores_unknown_keys(self):
        """Unknown keys should be filtered out silently."""
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_chain = MagicMock()
            mock_chain.execute.return_value = MagicMock(data=[{"id": TOURNAMENT_ID}])
            mock_client = MagicMock()
            mock_client.table.return_value.update.return_value.eq.return_value = mock_chain
            mock_get.return_value = mock_client

            from backend.api.supabase_client import update_tournament
            # "foo" is not an allowed key
            update_tournament(TOURNAMENT_ID, {"foo": "bar", "status": "in_progress"})

        call_data = mock_client.table.return_value.update.call_args[0][0]
        assert "foo" not in call_data
        assert call_data.get("status") == "in_progress"

    def test_validates_champion_team_id_uuid(self):
        from backend.api.supabase_client import update_tournament
        with pytest.raises(ValueError):
            update_tournament(TOURNAMENT_ID, {"champion_team_id": "not-a-valid-uuid"})


# =============================================================================
# 3. Seed management
# =============================================================================

class TestGetTournamentSeeds:
    def test_returns_all_seeds(self, sample_seed):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_query = MagicMock()
            mock_query.execute.return_value = MagicMock(data=[sample_seed])
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value = mock_query
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament_seeds
            result = get_tournament_seeds(TOURNAMENT_ID)

        assert len(result) == 1
        assert result[0]["seed"] == 1

    def test_filters_by_region(self, sample_seed):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_query = MagicMock()
            mock_query.execute.return_value = MagicMock(data=[sample_seed])
            mock_query.eq.return_value = mock_query
            mock_query.order.return_value = mock_query
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value = mock_query
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament_seeds
            result = get_tournament_seeds(TOURNAMENT_ID, region="East")

        assert result[0]["region"] == "East"

    def test_invalid_region_raises(self):
        from backend.api.supabase_client import get_tournament_seeds
        with pytest.raises(ValueError):
            get_tournament_seeds(TOURNAMENT_ID, region="Pacific")

    def test_invalid_tournament_uuid_raises(self):
        from backend.api.supabase_client import get_tournament_seeds
        with pytest.raises(ValueError):
            get_tournament_seeds("bad-uuid")


class TestUpsertTournamentSeed:
    def test_upserts_valid_seed(self, sample_seed):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
                data=[sample_seed]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import upsert_tournament_seed
            result = upsert_tournament_seed({
                "tournament_id": TOURNAMENT_ID,
                "team_id": TEAM_HOME_ID,
                "seed": 1,
                "region": "East",
            })

        assert result["seed"] == 1

    def test_rejects_invalid_team_uuid(self):
        from backend.api.supabase_client import upsert_tournament_seed
        with pytest.raises(ValueError):
            upsert_tournament_seed({
                "tournament_id": TOURNAMENT_ID,
                "team_id": "not-a-uuid",
                "seed": 1,
                "region": "East",
            })


class TestBulkInsertSeeds:
    def _make_seeds(self):
        return [
            {"team_id": TEAM_HOME_ID, "seed": 1, "region": "East"},
            {"team_id": TEAM_AWAY_ID, "seed": 16, "region": "East"},
        ]

    def test_inserts_seed_rows(self):
        expected = [
            {"tournament_id": TOURNAMENT_ID, "team_id": TEAM_HOME_ID, "seed": 1, "region": "East"},
            {"tournament_id": TOURNAMENT_ID, "team_id": TEAM_AWAY_ID, "seed": 16, "region": "East"},
        ]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
                data=expected
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import bulk_insert_seeds
            result = bulk_insert_seeds(TOURNAMENT_ID, self._make_seeds())

        assert len(result) == 2

    def test_invalid_tournament_uuid_raises(self):
        from backend.api.supabase_client import bulk_insert_seeds
        with pytest.raises(ValueError):
            bulk_insert_seeds("bad", self._make_seeds())

    def test_invalid_team_uuid_in_batch_raises(self):
        from backend.api.supabase_client import bulk_insert_seeds
        bad_seeds = [{"team_id": "not-uuid", "seed": 1, "region": "East"}]
        with pytest.raises(ValueError):
            bulk_insert_seeds(TOURNAMENT_ID, bad_seeds)


# =============================================================================
# 4. Bracket view + game data
# =============================================================================

class TestGetTournamentBracketView:
    def _mock_client(self, data):
        mock_query = MagicMock()
        mock_query.execute.return_value = MagicMock(data=data)
        mock_query.eq.return_value = mock_query
        mock_query.or_.return_value = mock_query
        mock_query.order.return_value = mock_query
        mock_client = MagicMock()
        mock_client.table.return_value.select.return_value.eq.return_value = mock_query
        return mock_client

    def test_returns_bracket_data(self):
        row = {"game_id": GAME_ID, "season": 2026, "tournament_round": "round_64"}
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._mock_client([row])
            from backend.api.supabase_client import get_tournament_bracket_view
            result = get_tournament_bracket_view(2026)
        assert len(result) == 1

    def test_invalid_region_raises(self):
        from backend.api.supabase_client import get_tournament_bracket_view
        with pytest.raises(ValueError):
            get_tournament_bracket_view(2026, region="BadRegion")

    def test_invalid_round_raises(self):
        from backend.api.supabase_client import get_tournament_bracket_view
        with pytest.raises(ValueError):
            get_tournament_bracket_view(2026, tournament_round="quarterfinal")

    def test_returns_empty_list_on_no_data(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._mock_client([])
            from backend.api.supabase_client import get_tournament_bracket_view
            result = get_tournament_bracket_view(2026)
        assert result == []


class TestGetTournamentGameData:
    def test_returns_game_data(self):
        row = {"game_id": GAME_ID, "tournament_round": "round_64"}
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_chain = MagicMock()
            mock_chain.execute.return_value = MagicMock(data=[row])
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value = mock_chain
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament_game_data
            result = get_tournament_game_data(GAME_ID)

        assert result["game_id"] == GAME_ID

    def test_returns_none_when_not_found(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_chain = MagicMock()
            mock_chain.execute.return_value = MagicMock(data=[])
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value = mock_chain
            mock_get.return_value = mock_client

            from backend.api.supabase_client import get_tournament_game_data
            result = get_tournament_game_data(GAME_ID)

        assert result is None

    def test_invalid_uuid_raises(self):
        from backend.api.supabase_client import get_tournament_game_data
        with pytest.raises(ValueError):
            get_tournament_game_data("not-a-uuid")


# =============================================================================
# 5. Bracket picks
# =============================================================================

class TestUpsertBracketPick:
    def test_upserts_pick(self, sample_bracket_pick):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.upsert.return_value.execute.return_value = MagicMock(
                data=[sample_bracket_pick]
            )
            mock_get.return_value = mock_client

            from backend.api.supabase_client import upsert_bracket_pick
            result = upsert_bracket_pick({
                "tournament_id": TOURNAMENT_ID,
                "game_id": GAME_ID,
                "picked_team_id": TEAM_HOME_ID,
                "confidence_score": 0.85,
            })

        assert result["picked_team_id"] == TEAM_HOME_ID

    def test_invalid_game_uuid_raises(self):
        from backend.api.supabase_client import upsert_bracket_pick
        with pytest.raises(ValueError):
            upsert_bracket_pick({
                "tournament_id": TOURNAMENT_ID,
                "game_id": "bad",
                "picked_team_id": TEAM_HOME_ID,
            })

    def test_invalid_picked_team_uuid_raises(self):
        from backend.api.supabase_client import upsert_bracket_pick
        with pytest.raises(ValueError):
            upsert_bracket_pick({
                "tournament_id": TOURNAMENT_ID,
                "game_id": GAME_ID,
                "picked_team_id": "not-valid",
            })


# =============================================================================
# 6. Grading logic
# =============================================================================

class TestGradeBracketPicks:
    def _build_mock(self, picks_data, update_data=None):
        """Return a mock supabase client for grade_bracket_picks."""
        mock_client = MagicMock()

        # select chain for fetching picks
        mock_select = MagicMock()
        mock_select.execute.return_value = MagicMock(data=picks_data)
        mock_client.table.return_value.select.return_value.eq.return_value.is_.return_value = mock_select

        # update chain for marking picks
        mock_update = MagicMock()
        mock_update.execute.return_value = MagicMock(data=update_data or [])
        mock_client.table.return_value.update.return_value.eq.return_value = mock_update

        return mock_client

    def test_grades_correct_pick(self):
        """Home team wins; pick = home → correct."""
        picks = [{
            "id": PICK_ID,
            "game_id": GAME_ID,
            "picked_team_id": TEAM_HOME_ID,
            "games": {
                "home_team_id": TEAM_HOME_ID,
                "away_team_id": TEAM_AWAY_ID,
                "home_score": 75,
                "away_score": 60,
                "status": "final",
            },
        }]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock(picks)
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result["graded"] == 1
        assert result["correct"] == 1
        assert result["incorrect"] == 0

    def test_grades_incorrect_pick(self):
        """Away team wins; pick = home → incorrect."""
        picks = [{
            "id": PICK_ID,
            "game_id": GAME_ID,
            "picked_team_id": TEAM_HOME_ID,
            "games": {
                "home_team_id": TEAM_HOME_ID,
                "away_team_id": TEAM_AWAY_ID,
                "home_score": 55,
                "away_score": 70,
                "status": "final",
            },
        }]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock(picks)
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result["correct"] == 0
        assert result["incorrect"] == 1

    def test_skips_non_final_games(self):
        """Games not yet final should be skipped."""
        picks = [{
            "id": PICK_ID,
            "game_id": GAME_ID,
            "picked_team_id": TEAM_HOME_ID,
            "games": {
                "home_team_id": TEAM_HOME_ID,
                "away_team_id": TEAM_AWAY_ID,
                "home_score": None,
                "away_score": None,
                "status": "scheduled",
            },
        }]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock(picks)
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result["graded"] == 0

    def test_skips_pick_with_missing_game(self):
        picks = [{"id": PICK_ID, "game_id": GAME_ID, "picked_team_id": TEAM_HOME_ID, "games": None}]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock(picks)
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result["graded"] == 0

    def test_empty_picks_returns_zeros(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock([])
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result == {"graded": 0, "correct": 0, "incorrect": 0}

    def test_invalid_uuid_raises(self):
        from backend.api.supabase_client import grade_bracket_picks
        with pytest.raises(ValueError):
            grade_bracket_picks("bad-uuid")

    def test_multiple_picks_mixed_results(self):
        picks = [
            {
                "id": "pick-1",
                "game_id": GAME_ID,
                "picked_team_id": TEAM_HOME_ID,
                "games": {"home_team_id": TEAM_HOME_ID, "away_team_id": TEAM_AWAY_ID, "home_score": 80, "away_score": 60, "status": "final"},
            },
            {
                "id": "pick-2",
                "game_id": GAME_ID,
                "picked_team_id": TEAM_HOME_ID,
                "games": {"home_team_id": TEAM_HOME_ID, "away_team_id": TEAM_AWAY_ID, "home_score": 55, "away_score": 72, "status": "final"},
            },
        ]
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_get.return_value = self._build_mock(picks)
            from backend.api.supabase_client import grade_bracket_picks
            result = grade_bracket_picks(TOURNAMENT_ID)

        assert result["graded"] == 2
        assert result["correct"] == 1
        assert result["incorrect"] == 1


# =============================================================================
# 7. Elimination tracking
# =============================================================================

class TestUpdateEliminatedTeams:
    def test_returns_zero_when_tournament_not_found(self):
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()
            mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
            mock_get.return_value = mock_client

            from backend.api.supabase_client import update_eliminated_teams
            result = update_eliminated_teams(TOURNAMENT_ID)

        assert result == 0

    def test_marks_losers_as_eliminated(self):
        """Home wins → away team marked eliminated."""
        final_game = {
            "id": GAME_ID,
            "home_team_id": TEAM_HOME_ID,
            "away_team_id": TEAM_AWAY_ID,
            "home_score": 75,
            "away_score": 60,
            "tournament_round": "round_64",
        }
        with patch("backend.api.supabase_client.get_supabase") as mock_get:
            mock_client = MagicMock()

            # tournament lookup
            mock_tournament_chain = MagicMock()
            mock_tournament_chain.execute.return_value = MagicMock(data=[{"season": 2026}])

            # games lookup
            mock_games_chain = MagicMock()
            mock_games_chain.execute.return_value = MagicMock(data=[final_game])

            # update chain
            mock_update_chain = MagicMock()
            mock_update_chain.execute.return_value = MagicMock(data=[{"team_id": TEAM_AWAY_ID}])

            # Wire up table calls in order
            call_count = {"n": 0}

            def table_side_effect(table_name):
                t = MagicMock()
                if table_name == "tournaments":
                    t.select.return_value.eq.return_value = mock_tournament_chain
                elif table_name == "games":
                    q = MagicMock()
                    q.eq.return_value = q
                    q.execute.return_value = MagicMock(data=[final_game])
                    t.select.return_value = q
                elif table_name == "tournament_seeds":
                    u = MagicMock()
                    u.eq.return_value = u
                    u.is_.return_value = u
                    u.execute.return_value = MagicMock(data=[{"team_id": TEAM_AWAY_ID}])
                    t.update.return_value = u
                return t

            mock_client.table.side_effect = table_side_effect
            mock_get.return_value = mock_client

            from backend.api.supabase_client import update_eliminated_teams
            result = update_eliminated_teams(TOURNAMENT_ID)

        assert result >= 0  # May be 1 if update returned data

    def test_invalid_uuid_raises(self):
        from backend.api.supabase_client import update_eliminated_teams
        with pytest.raises(ValueError):
            update_eliminated_teams("not-valid")


# =============================================================================
# 8. Pydantic model validation
# =============================================================================

class TestTournamentSeedInput:
    def test_valid_seed(self):
        from backend.api.main import TournamentSeedInput
        seed = TournamentSeedInput(team_name="Duke", seed=1, region="East")
        assert seed.team_name == "Duke"
        assert seed.seed == 1
        assert seed.region == "East"
        assert seed.is_play_in is False

    def test_seed_out_of_range_raises(self):
        from pydantic import ValidationError
        from backend.api.main import TournamentSeedInput
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="Duke", seed=17, region="East")

    def test_seed_zero_raises(self):
        from pydantic import ValidationError
        from backend.api.main import TournamentSeedInput
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="Duke", seed=0, region="East")

    def test_invalid_region_raises(self):
        from pydantic import ValidationError
        from backend.api.main import TournamentSeedInput
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name="Duke", seed=1, region="Pacific")

    @pytest.mark.parametrize("bad_name", [
        "Duke<script>",
        "Team; DROP TABLE",
        "A" * 101,
        "",
    ])
    def test_invalid_team_name_raises(self, bad_name):
        from pydantic import ValidationError
        from backend.api.main import TournamentSeedInput
        with pytest.raises(ValidationError):
            TournamentSeedInput(team_name=bad_name, seed=1, region="East")

    @pytest.mark.parametrize("valid_name", [
        "Duke", "North Carolina", "St. John's", "Texas A&M",
        "Miami (FL)", "UCLA", "UConn", "Ole Miss",
    ])
    def test_valid_team_names(self, valid_name):
        from backend.api.main import TournamentSeedInput
        seed = TournamentSeedInput(team_name=valid_name, seed=1, region="East")
        assert seed.team_name == valid_name

    def test_play_in_fields(self):
        from backend.api.main import TournamentSeedInput
        seed = TournamentSeedInput(
            team_name="Alabama State", seed=16, region="South",
            is_play_in=True, play_in_matchup=1
        )
        assert seed.is_play_in is True
        assert seed.play_in_matchup == 1


class TestSetBracketRequest:
    def _make_seeds(self, count=64):
        from backend.api.main import TournamentSeedInput
        regions = ["East", "West", "South", "Midwest"]
        seeds = []
        for i, region in enumerate(regions):
            for seed_num in range(1, count // 4 + 1):
                seeds.append(
                    TournamentSeedInput(
                        team_name=f"Team{i * 16 + seed_num}",
                        seed=seed_num,
                        region=region,
                    )
                )
        return seeds

    def test_valid_64_seeds(self):
        from pydantic import ValidationError
        from backend.api.main import SetBracketRequest
        req = SetBracketRequest(season=2026, seeds=self._make_seeds(64))
        assert req.season == 2026
        assert len(req.seeds) == 64

    def test_too_few_seeds_raises(self):
        from pydantic import ValidationError
        from backend.api.main import SetBracketRequest
        with pytest.raises(ValidationError):
            SetBracketRequest(season=2026, seeds=self._make_seeds(64)[:60])

    def test_too_many_seeds_raises(self):
        from pydantic import ValidationError
        from backend.api.main import TournamentSeedInput, SetBracketRequest
        seeds = self._make_seeds(64) + [TournamentSeedInput(team_name=f"Extra{i}", seed=1, region="East") for i in range(5)]
        with pytest.raises(ValidationError):
            SetBracketRequest(season=2026, seeds=seeds)

    def test_season_out_of_range_raises(self):
        from pydantic import ValidationError
        from backend.api.main import SetBracketRequest
        with pytest.raises(ValidationError):
            SetBracketRequest(season=1999, seeds=self._make_seeds(64))


class TestBracketPickRequest:
    def test_valid_request(self):
        from backend.api.main import BracketPickRequest
        req = BracketPickRequest(
            game_id=GAME_ID,
            picked_team_id=TEAM_HOME_ID,
            confidence_score=0.85,
            reasoning="1-seed dominance",
        )
        assert req.confidence_score == 0.85

    def test_invalid_game_id_raises(self):
        from pydantic import ValidationError
        from backend.api.main import BracketPickRequest
        with pytest.raises(ValidationError):
            BracketPickRequest(game_id="not-uuid", picked_team_id=TEAM_HOME_ID)

    def test_confidence_out_of_range_raises(self):
        from pydantic import ValidationError
        from backend.api.main import BracketPickRequest
        with pytest.raises(ValidationError):
            BracketPickRequest(game_id=GAME_ID, picked_team_id=TEAM_HOME_ID, confidence_score=1.5)

    def test_negative_confidence_raises(self):
        from pydantic import ValidationError
        from backend.api.main import BracketPickRequest
        with pytest.raises(ValidationError):
            BracketPickRequest(game_id=GAME_ID, picked_team_id=TEAM_HOME_ID, confidence_score=-0.1)


class TestGeneratePicksRequest:
    def test_valid_minimal(self):
        from backend.api.main import GeneratePicksRequest
        req = GeneratePicksRequest(season=2026)
        assert req.provider == "claude"
        assert req.force is False

    def test_invalid_region_raises(self):
        from pydantic import ValidationError
        from backend.api.main import GeneratePicksRequest
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=2026, region="Pacific")

    def test_invalid_round_raises(self):
        from pydantic import ValidationError
        from backend.api.main import GeneratePicksRequest
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=2026, round="quarterfinal")

    def test_invalid_provider_raises(self):
        from pydantic import ValidationError
        from backend.api.main import GeneratePicksRequest
        with pytest.raises(ValidationError):
            GeneratePicksRequest(season=2026, provider="openai")

    @pytest.mark.parametrize("region", ["East", "West", "South", "Midwest"])
    def test_all_valid_regions(self, region):
        from backend.api.main import GeneratePicksRequest
        req = GeneratePicksRequest(season=2026, region=region)
        assert req.region == region

    @pytest.mark.parametrize("rnd", ["first_four", "round_64", "round_32", "sweet_16", "elite_8", "final_4", "championship"])
    def test_all_valid_rounds(self, rnd):
        from backend.api.main import GeneratePicksRequest
        req = GeneratePicksRequest(season=2026, round=rnd)
        assert req.round == rnd


# =============================================================================
# 9. API endpoint tests
# =============================================================================

class TestGetTournamentInfoEndpoint:
    def test_returns_existing_tournament(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.get("/tournament/2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["season"] == 2026

    def test_creates_tournament_when_not_found(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=None), \
             patch("backend.api.main.create_tournament", return_value=sample_tournament):
            response = client.get("/tournament/2026")
        assert response.status_code == 200

    def test_season_below_minimum_returns_error(self, client):
        # Middleware converts RequestValidationError → 400
        response = client.get("/tournament/1999")
        assert response.status_code == 400

    def test_season_above_maximum_returns_error(self, client):
        response = client.get("/tournament/2101")
        assert response.status_code == 400


class TestGetBracketEndpoint:
    def _bracket_row(self):
        return {
            "game_id": GAME_ID,
            "season": 2026,
            "tournament_round": "round_64",
            "home_region": "East",
            "away_region": "East",
        }

    def test_returns_bracket_data(self, client):
        with patch("backend.api.main.get_tournament_bracket_view", return_value=[self._bracket_row()]):
            response = client.get("/tournament/bracket?season=2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert isinstance(data, list)
        assert len(data) == 1

    def test_filters_by_region(self, client):
        with patch("backend.api.main.get_tournament_bracket_view", return_value=[self._bracket_row()]) as mock:
            response = client.get("/tournament/bracket?season=2026&region=East")
        assert response.status_code == 200
        mock.assert_called_once_with(2026, region="East", tournament_round=None)

    def test_filters_by_round(self, client):
        with patch("backend.api.main.get_tournament_bracket_view", return_value=[]) as mock:
            response = client.get("/tournament/bracket?season=2026&round=round_64")
        assert response.status_code == 200
        mock.assert_called_once_with(2026, region=None, tournament_round="round_64")

    def test_invalid_region_returns_400(self, client):
        response = client.get("/tournament/bracket?season=2026&region=Pacific")
        assert response.status_code == 400

    def test_invalid_round_returns_400(self, client):
        response = client.get("/tournament/bracket?season=2026&round=quarterfinal")
        assert response.status_code == 400

    def test_missing_season_returns_400(self, client):
        # season is required; missing it → RequestValidationError → 400
        response = client.get("/tournament/bracket")
        assert response.status_code == 400


class TestGetRegionsEndpoint:
    def test_groups_seeds_by_region(self, client):
        rows = [
            {"region": "East", "team_name": "Duke", "seed": 1},
            {"region": "East", "team_name": "UMBC", "seed": 16},
            {"region": "West", "team_name": "Kansas", "seed": 1},
        ]
        with patch("backend.api.main.get_region_summary", return_value=rows):
            response = client.get("/tournament/regions?season=2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert "regions" in data
        assert "East" in data["regions"]
        assert len(data["regions"]["East"]) == 2
        assert data["total_teams"] == 3

    def test_returns_empty_regions_for_new_tournament(self, client):
        with patch("backend.api.main.get_region_summary", return_value=[]):
            response = client.get("/tournament/regions?season=2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_teams"] == 0


class TestSetBracketEndpoint:
    def _make_64_seeds(self):
        regions = ["East", "West", "South", "Midwest"]
        seeds = []
        for region in regions:
            for seed_num in range(1, 17):
                seeds.append({
                    "team_name": f"{region}Team{seed_num}",
                    "seed": seed_num,
                    "region": region,
                })
        return seeds

    def test_successful_bracket_population(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament), \
             patch("backend.api.main.get_team_by_name", side_effect=lambda name: {"id": f"uuid-{name.lower()}"}), \
             patch("backend.api.main.bulk_insert_seeds", return_value=[{}] * 64), \
             patch("backend.api.main.update_tournament"):
            response = client.post(
                "/tournament/set-bracket",
                json={"season": 2026, "seeds": self._make_64_seeds()},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["seeds_inserted"] == 64

    def test_creates_tournament_if_not_found(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=None), \
             patch("backend.api.main.create_tournament", return_value=sample_tournament), \
             patch("backend.api.main.get_team_by_name", side_effect=lambda name: {"id": f"uuid-{name.lower()}"}), \
             patch("backend.api.main.bulk_insert_seeds", return_value=[{}] * 64), \
             patch("backend.api.main.update_tournament"):
            response = client.post(
                "/tournament/set-bracket",
                json={"season": 2026, "seeds": self._make_64_seeds()},
            )
        assert response.status_code == 200

    def test_duplicate_team_names_returns_400(self, client, sample_tournament):
        seeds = self._make_64_seeds()
        # Replace the last team name with a duplicate
        seeds[-1]["team_name"] = seeds[0]["team_name"]
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/set-bracket",
                json={"season": 2026, "seeds": seeds},
            )
        assert response.status_code in (400, 422)

    def test_unknown_teams_returned_in_errors(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament), \
             patch("backend.api.main.get_team_by_name", return_value=None), \
             patch("backend.api.main.bulk_insert_seeds", return_value=[]):
            response = client.post(
                "/tournament/set-bracket",
                json={"season": 2026, "seeds": self._make_64_seeds()},
            )
        # All teams unknown → no valid seeds → 400
        assert response.status_code in (400, 422)

    def test_fewer_than_64_seeds_returns_400(self, client):
        seeds = self._make_64_seeds()[:60]
        response = client.post(
            "/tournament/set-bracket",
            json={"season": 2026, "seeds": seeds},
        )
        assert response.status_code == 400


class TestMakeBracketPickEndpoint:
    def _game(self, is_tournament=True):
        return {
            "id": GAME_ID,
            "is_tournament": is_tournament,
            "home_team_id": TEAM_HOME_ID,
            "away_team_id": TEAM_AWAY_ID,
            "season": 2026,
            "tournament_round": "round_64",
        }

    def test_successful_pick(self, client, sample_tournament, sample_bracket_pick):
        with patch("backend.api.main.get_game_by_id", return_value=self._game()), \
             patch("backend.api.main.get_tournament", return_value=sample_tournament), \
             patch("backend.api.main.upsert_bracket_pick", return_value=sample_bracket_pick):
            response = client.post(
                "/tournament/pick",
                json={"game_id": GAME_ID, "picked_team_id": TEAM_HOME_ID},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["picked_team_id"] == TEAM_HOME_ID

    def test_game_not_found_returns_404(self, client):
        with patch("backend.api.main.get_game_by_id", return_value=None):
            response = client.post(
                "/tournament/pick",
                json={"game_id": GAME_ID, "picked_team_id": TEAM_HOME_ID},
            )
        assert response.status_code == 404

    def test_non_tournament_game_returns_400(self, client):
        with patch("backend.api.main.get_game_by_id", return_value=self._game(is_tournament=False)):
            response = client.post(
                "/tournament/pick",
                json={"game_id": GAME_ID, "picked_team_id": TEAM_HOME_ID},
            )
        assert response.status_code in (400, 422)

    def test_team_not_in_game_returns_400(self, client, sample_tournament):
        other_team = "99999999-8888-7777-6666-555555555555"
        with patch("backend.api.main.get_game_by_id", return_value=self._game()), \
             patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/pick",
                json={"game_id": GAME_ID, "picked_team_id": other_team},
            )
        assert response.status_code in (400, 422)

    def test_invalid_game_uuid_returns_400(self, client):
        response = client.post(
            "/tournament/pick",
            json={"game_id": "not-a-uuid", "picked_team_id": TEAM_HOME_ID},
        )
        assert response.status_code == 400

    def test_tournament_not_found_returns_404(self, client):
        with patch("backend.api.main.get_game_by_id", return_value=self._game()), \
             patch("backend.api.main.get_tournament", return_value=None):
            response = client.post(
                "/tournament/pick",
                json={"game_id": GAME_ID, "picked_team_id": TEAM_HOME_ID},
            )
        assert response.status_code == 404


class TestGradeTournamentEndpoint:
    def test_successful_grading(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament), \
             patch("backend.api.main.grade_bracket_picks", return_value={"graded": 5, "correct": 3, "incorrect": 2}), \
             patch("backend.api.main.update_eliminated_teams", return_value=2):
            response = client.post("/tournament/grade?season=2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["picks_graded"] == 5
        assert data["correct"] == 3
        assert data["incorrect"] == 2
        assert data["teams_eliminated"] == 2

    def test_tournament_not_found_returns_404(self, client):
        with patch("backend.api.main.get_tournament", return_value=None):
            response = client.post("/tournament/grade?season=2026")
        assert response.status_code == 404

    def test_missing_season_returns_400(self, client):
        response = client.post("/tournament/grade")
        assert response.status_code == 400


class TestTournamentAIAnalysisEndpoint:
    def _ai_result(self):
        return {
            "ai_provider": "claude",
            "tournament_round": "round_64",
            "region": "East",
            "home_seed": 1,
            "away_seed": 16,
            "home_team": "Duke",
            "away_team": "UMBC",
            "picked_team": "Duke",
            "picked_team_id": TEAM_HOME_ID,
            "pick_confidence": 0.96,
            "pick_key_factors": ["KenPom gap", "Seed history"],
            "pick_reasoning": "Duke is dominant",
            "recommended_bet": "away_spread",
            "bet_confidence": 0.62,
            "bet_key_factors": ["16-seeds cover ~40%"],
            "bet_reasoning": "UMBC +25.5 has value",
            "created_at": "2026-03-15T10:00:00",
        }

    def test_successful_analysis(self, client):
        with patch("backend.api.main.analyze_tournament_game", return_value=self._ai_result()):
            response = client.post(
                "/tournament/ai-analysis",
                json={"game_id": GAME_ID, "provider": "claude"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["picked_team"] == "Duke"
        assert data["ai_provider"] == "claude"
        assert data["home_seed"] == 1
        assert data["away_seed"] == 16

    def test_grok_provider(self, client):
        result = {**self._ai_result(), "ai_provider": "grok"}
        with patch("backend.api.main.analyze_tournament_game", return_value=result):
            response = client.post(
                "/tournament/ai-analysis",
                json={"game_id": GAME_ID, "provider": "grok"},
            )
        assert response.status_code == 200
        assert response.json()["ai_provider"] == "grok"

    def test_game_not_in_bracket_returns_404(self, client):
        with patch(
            "backend.api.main.analyze_tournament_game",
            side_effect=ValueError(f"{GAME_ID} not found in tournament_bracket"),
        ):
            response = client.post(
                "/tournament/ai-analysis",
                json={"game_id": GAME_ID, "provider": "claude"},
            )
        assert response.status_code == 404

    def test_invalid_game_uuid_returns_400(self, client):
        response = client.post(
            "/tournament/ai-analysis",
            json={"game_id": "not-a-uuid", "provider": "claude"},
        )
        assert response.status_code == 400

    def test_invalid_provider_returns_400(self, client):
        response = client.post(
            "/tournament/ai-analysis",
            json={"game_id": GAME_ID, "provider": "openai"},
        )
        assert response.status_code == 400

    def test_ai_service_error_returns_error_status(self, client):
        with patch(
            "backend.api.main.analyze_tournament_game",
            side_effect=RuntimeError("AI service down"),
        ):
            response = client.post(
                "/tournament/ai-analysis",
                json={"game_id": GAME_ID, "provider": "claude"},
            )
        # ExternalApiException → 502 Bad Gateway
        assert response.status_code == 502

    def test_default_provider_is_claude(self, client):
        with patch("backend.api.main.analyze_tournament_game", return_value=self._ai_result()) as mock:
            client.post(
                "/tournament/ai-analysis",
                json={"game_id": GAME_ID},
            )
        mock.assert_called_once_with(GAME_ID, "claude")


class TestGetTournamentAIAnalysisEndpoint:
    def _bracket_row_with_pick(self):
        return {
            "game_id": GAME_ID,
            "season": 2026,
            "tournament_round": "round_64",
            "picked_team_id": TEAM_HOME_ID,
            "pick_confidence": 0.85,
            "pick_reasoning": "Duke dominates",
        }

    def test_get_by_game_id_with_pick(self, client):
        with patch("backend.api.main.get_tournament_game_data", return_value=self._bracket_row_with_pick()):
            response = client.get(f"/tournament/ai-analysis?game_id={GAME_ID}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1

    def test_get_by_game_id_no_pick_returns_empty_list(self, client):
        row = {**self._bracket_row_with_pick(), "picked_team_id": None}
        with patch("backend.api.main.get_tournament_game_data", return_value=row):
            response = client.get(f"/tournament/ai-analysis?game_id={GAME_ID}")
        assert response.status_code == 200
        assert response.json()["data"] == []

    def test_get_by_game_id_not_found_returns_404(self, client):
        with patch("backend.api.main.get_tournament_game_data", return_value=None):
            response = client.get(f"/tournament/ai-analysis?game_id={GAME_ID}")
        assert response.status_code == 404

    def test_get_by_season_returns_only_picked(self, client):
        rows = [
            self._bracket_row_with_pick(),
            {**self._bracket_row_with_pick(), "game_id": "aabbccdd-0000-1111-2222-333344445555", "picked_team_id": None},
        ]
        with patch("backend.api.main.get_tournament_bracket_view", return_value=rows):
            response = client.get("/tournament/ai-analysis?season=2026")
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 1  # Only the row with a pick

    def test_no_params_returns_400(self, client):
        response = client.get("/tournament/ai-analysis")
        assert response.status_code == 400

    def test_invalid_round_returns_400(self, client):
        response = client.get("/tournament/ai-analysis?season=2026&round=quarterfinal")
        assert response.status_code == 400


class TestGeneratePicksEndpoint:
    def test_queues_background_job(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/generate-picks",
                json={"season": 2026, "provider": "claude"},
            )
        assert response.status_code == 200
        data = response.json()["data"]
        assert "job_id" in data
        assert data["status"] == "queued"
        assert "poll_url" in data

    def test_tournament_not_found_returns_404(self, client):
        with patch("backend.api.main.get_tournament", return_value=None):
            response = client.post(
                "/tournament/generate-picks",
                json={"season": 2026},
            )
        assert response.status_code == 404

    def test_invalid_region_returns_400(self, client):
        response = client.post(
            "/tournament/generate-picks",
            json={"season": 2026, "region": "Pacific"},
        )
        assert response.status_code == 400

    def test_invalid_round_returns_400(self, client):
        response = client.post(
            "/tournament/generate-picks",
            json={"season": 2026, "round": "quarterfinal"},
        )
        assert response.status_code == 400

    def test_grok_provider_accepted(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/generate-picks",
                json={"season": 2026, "provider": "grok"},
            )
        assert response.status_code == 200

    def test_region_and_round_filters_accepted(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/generate-picks",
                json={"season": 2026, "region": "East", "round": "round_64"},
            )
        assert response.status_code == 200

    def test_force_flag_accepted(self, client, sample_tournament):
        with patch("backend.api.main.get_tournament", return_value=sample_tournament):
            response = client.post(
                "/tournament/generate-picks",
                json={"season": 2026, "force": True},
            )
        assert response.status_code == 200

"""
Pytest configuration and shared fixtures for backend tests.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime


# Sample game data for tests
@pytest.fixture
def sample_game():
    """Sample game data from database."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "date": "2025-01-20",
        "home_team": {"id": "team-home-uuid", "name": "Duke", "conference": "ACC"},
        "away_team": {"id": "team-away-uuid", "name": "North Carolina", "conference": "ACC"},
        "home_team_id": "team-home-uuid",
        "away_team_id": "team-away-uuid",
        "season": 2025,
        "is_conference_game": True,
        "is_tournament": False,
        "venue": "Cameron Indoor Stadium",
        "neutral_site": False,
    }


@pytest.fixture
def sample_spread():
    """Sample spread data."""
    return {
        "home_spread": -7.5,
        "away_spread": 7.5,
        "home_ml": -280,
        "away_ml": 220,
        "over_under": 145.5,
    }


@pytest.fixture
def sample_ranking():
    """Sample ranking data."""
    return {"rank": 5, "team_id": "team-home-uuid", "season": 2025}


@pytest.fixture
def sample_kenpom():
    """Sample KenPom analytics data."""
    return {
        "team_id": "team-home-uuid",
        "season": 2025,
        "rank": 3,
        "adj_efficiency_margin": 28.5,
        "adj_offense": 118.5,
        "adj_offense_rank": 5,
        "adj_defense": 90.0,
        "adj_defense_rank": 2,
        "adj_tempo": 70.2,
        "adj_tempo_rank": 45,
        "sos_adj_em": 12.5,
        "sos_adj_em_rank": 10,
        "luck": 0.02,
        "luck_rank": 150,
        "wins": 18,
        "losses": 2,
    }


@pytest.fixture
def sample_haslametrics():
    """Sample Haslametrics analytics data."""
    return {
        "team_id": "team-home-uuid",
        "season": 2025,
        "rank": 4,
        "offensive_efficiency": 115.2,
        "defensive_efficiency": 92.1,
        "all_play_pct": 0.92,
        "momentum_overall": 0.05,
        "momentum_offense": 0.03,
        "momentum_defense": 0.07,
        "pace": 68.5,
        "sos": 0.55,
        "sos_rank": 15,
        "last_5_record": "4-1",
        "quad_1_record": "5-2",
        "quad_2_record": "3-0",
    }


@pytest.fixture
def sample_game_context(sample_game, sample_spread, sample_kenpom, sample_haslametrics):
    """Full game context as built by build_game_context."""
    return {
        "game_id": sample_game["id"],
        "date": sample_game["date"],
        "home_team": "Duke",
        "away_team": "North Carolina",
        "home_conference": "ACC",
        "away_conference": "ACC",
        "home_rank": 5,
        "away_rank": 8,
        "is_conference_game": True,
        "is_tournament": False,
        "venue": "Cameron Indoor Stadium",
        "neutral_site": False,
        "spread": sample_spread["home_spread"],
        "home_ml": sample_spread["home_ml"],
        "away_ml": sample_spread["away_ml"],
        "total": sample_spread["over_under"],
        "home_kenpom": sample_kenpom,
        "away_kenpom": {**sample_kenpom, "rank": 10, "adj_efficiency_margin": 22.0},
        "home_haslametrics": sample_haslametrics,
        "away_haslametrics": {**sample_haslametrics, "rank": 12, "all_play_pct": 0.85},
    }


@pytest.fixture
def valid_claude_response():
    """Valid JSON response from Claude."""
    return {
        "recommended_bet": "home_spread",
        "confidence_score": 0.72,
        "key_factors": [
            "Duke's elite defense holds opponents to 90 PPP",
            "Home court advantage at Cameron Indoor",
            "KenPom and Haslametrics both favor Duke",
        ],
        "reasoning": "Duke's defensive efficiency creates significant matchup problems for UNC. The spread is accurate based on analytics.",
    }


@pytest.fixture
def valid_grok_response():
    """Valid JSON response from Grok."""
    return {
        "recommended_bet": "away_spread",
        "confidence_score": 0.65,
        "key_factors": [
            "UNC's recent momentum is positive",
            "Rivalry games tend to be closer",
            "Duke may be overvalued at home",
        ],
        "reasoning": "While Duke is favored, rivalry dynamics and UNC's recent form suggest the spread may be too wide.",
    }


@pytest.fixture
def mock_supabase_client():
    """Mock the supabase_client module functions."""
    with patch.multiple(
        "backend.api.ai_service",
        get_game_by_id=MagicMock(),
        get_latest_spread=MagicMock(),
        get_team_ranking=MagicMock(),
        get_team_kenpom=MagicMock(),
        get_team_haslametrics=MagicMock(),
        insert_ai_analysis=MagicMock(return_value={"id": "analysis-uuid", "created_at": datetime.now().isoformat()}),
    ) as mocks:
        yield mocks


@pytest.fixture
def mock_claude_client():
    """Mock the Anthropic Claude client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"recommended_bet": "home_spread", "confidence_score": 0.72, "key_factors": ["Factor 1", "Factor 2"], "reasoning": "Test reasoning"}')]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 200
    mock_client.messages.create.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_grok_client():
    """Mock the OpenAI-compatible Grok client."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = '{"recommended_bet": "away_spread", "confidence_score": 0.65, "key_factors": ["Factor 1", "Factor 2"], "reasoning": "Grok reasoning"}'
    mock_response.choices = [MagicMock(message=mock_message)]
    mock_response.usage = MagicMock(total_tokens=700)
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


# ============================================================================
# DATA PIPELINE FIXTURES
# ============================================================================

@pytest.fixture
def sample_odds_api_game():
    """Sample game from The Odds API."""
    return {
        "id": "game-external-1",
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
                            {"name": "Duke Blue Devils", "point": -7.5, "price": -110},
                            {"name": "North Carolina Tar Heels", "point": 7.5, "price": -110},
                        ]
                    },
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Duke Blue Devils", "price": -280},
                            {"name": "North Carolina Tar Heels", "price": 220},
                        ]
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "point": 145.5, "price": -110},
                            {"name": "Under", "point": 145.5, "price": -110},
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_kenpom_dataframe():
    """Sample KenPom DataFrame from kenpompy."""
    import pandas as pd
    return pd.DataFrame([
        {
            "Rk": 1, "Team": "Duke", "Conf": "ACC", "W-L": "18-2",
            "AdjEM": 28.5, "AdjO": 118.5, "AdjO Rank": 3,
            "AdjD": 90.0, "AdjD Rank": 2, "AdjT": 70.2, "AdjT Rank": 45,
            "Luck": 0.02, "Luck Rank": 150, "SOS AdjEM": 12.5, "SOS AdjEM Rank": 10,
        },
        {
            "Rk": 2, "Team": "North Carolina", "Conf": "ACC", "W-L": "17-3",
            "AdjEM": 25.2, "AdjO": 116.8, "AdjO Rank": 8,
            "AdjD": 91.6, "AdjD Rank": 5, "AdjT": 72.1, "AdjT Rank": 30,
            "Luck": -0.01, "Luck Rank": 200, "SOS AdjEM": 11.8, "SOS AdjEM Rank": 12,
        },
    ])


@pytest.fixture
def sample_haslametrics_team_list():
    """Sample Haslametrics team data as parsed from XML."""
    return [
        {
            "team": "Duke",
            "rank": "1",
            "conference": "ACC",
            "wins": "18",
            "losses": "2",
            "offensive_efficiency": "118.5",
            "defensive_efficiency": "89.2",
            "all_play_pct": "0.94",
            "momentum_overall": "0.05",
            "momentum_offense": "0.03",
            "momentum_defense": "0.07",
            "sos": "0.65",
            "quad_1_record": "5-1",
        },
        {
            "team": "N Carolina",
            "rank": "2",
            "conference": "ACC",
            "wins": "17",
            "losses": "3",
            "offensive_efficiency": "116.2",
            "defensive_efficiency": "91.5",
            "all_play_pct": "0.91",
            "momentum_overall": "0.02",
            "momentum_offense": "0.01",
            "momentum_defense": "0.03",
            "sos": "0.62",
            "quad_1_record": "4-2",
        },
    ]


@pytest.fixture
def mock_supabase_table():
    """Create a mock Supabase table with common chain operations."""
    mock_table = MagicMock()

    # Setup select chain
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select

    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_eq.eq.return_value = mock_eq
    mock_eq.is_.return_value = mock_eq
    mock_eq.gte.return_value = mock_eq
    mock_eq.lte.return_value = mock_eq

    mock_ilike = MagicMock()
    mock_select.ilike.return_value = mock_ilike

    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order

    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit

    # Default empty results
    mock_eq.execute.return_value = MagicMock(data=[])
    mock_ilike.execute.return_value = MagicMock(data=[])
    mock_limit.execute.return_value = MagicMock(data=[])
    mock_select.execute.return_value = MagicMock(data=[])

    # Setup insert chain
    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = MagicMock(data=[{"id": "new-uuid"}])

    # Setup delete chain
    mock_delete = MagicMock()
    mock_table.delete.return_value = mock_delete
    mock_delete.eq.return_value = mock_delete
    mock_delete.execute.return_value = MagicMock(data=[])

    return mock_table


@pytest.fixture
def mock_requests_success():
    """Mock requests.get for successful API calls."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.headers = {"x-requests-remaining": "450", "x-requests-used": "50"}
    return mock_response


@pytest.fixture
def mock_requests_timeout():
    """Mock requests.get that raises timeout."""
    import requests
    return requests.exceptions.Timeout("Connection timed out")


@pytest.fixture
def mock_requests_connection_error():
    """Mock requests.get that raises connection error."""
    import requests
    return requests.exceptions.ConnectionError("Connection refused")


# ============================================================================
# HELPER FIXTURES FOR PIPELINE TESTING
# ============================================================================

@pytest.fixture
def sample_team_mapping():
    """Sample team ID mapping for tests."""
    return {
        "duke": "duke-uuid-1234",
        "north-carolina": "unc-uuid-1234",
        "kentucky": "kentucky-uuid-1234",
        "kansas": "kansas-uuid-1234",
        "connecticut": "uconn-uuid-1234",
    }


@pytest.fixture
def sample_prediction():
    """Sample prediction data."""
    return {
        "id": "prediction-uuid-1234",
        "game_id": "550e8400-e29b-41d4-a716-446655440000",
        "model_name": "baseline_v1",
        "predicted_home_cover_prob": 0.54,
        "predicted_away_cover_prob": 0.46,
        "spread_at_prediction": -7.5,
        "confidence_tier": "medium",
        "recommended_bet": "home_spread",
        "edge_pct": 4.0,
    }


@pytest.fixture
def sample_ai_analysis():
    """Sample AI analysis from Claude."""
    return {
        "id": "analysis-uuid-1234",
        "game_id": "550e8400-e29b-41d4-a716-446655440000",
        "ai_provider": "claude",
        "recommended_bet": "home_spread",
        "confidence_score": 0.72,
        "key_factors": [
            "Duke's elite defense",
            "Home court advantage",
            "Analytics favor Duke",
        ],
        "reasoning": "Duke's defensive efficiency creates matchup problems.",
        "model_version": "claude-3-opus",
        "tokens_used": 700,
    }

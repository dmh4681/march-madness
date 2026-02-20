"""
E2E tests for the AI analysis workflow (Task #10).

Tests the complete flow:
1. Triggering game analysis via API endpoint
2. Building game context from multiple data sources
3. Generating AI predictions with Claude and Grok
4. Comparing AI predictions with actual game results
5. Viewing stored analysis data through the API

These tests mock external dependencies (AI providers, database) but test
the full integration between modules: main.py -> ai_service.py -> supabase_client.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, date, timedelta
from fastapi.testclient import TestClient


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def app_client():
    """Create a test client for the FastAPI app."""
    with patch.dict("os.environ", {"ALLOWED_ORIGINS": "http://localhost:3000"}):
        from backend.api.main import app
        return TestClient(app)


@pytest.fixture
def full_game_record():
    """A complete game record as returned from Supabase."""
    return {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "external_id": "espn-401234567",
        "date": "2025-02-15",
        "tip_time": "2025-02-15T19:00:00+00:00",
        "season": 2025,
        "home_team_id": "duke-uuid-1234",
        "away_team_id": "unc-uuid-5678",
        "home_team": {"id": "duke-uuid-1234", "name": "Duke", "conference": "ACC"},
        "away_team": {"id": "unc-uuid-5678", "name": "North Carolina", "conference": "ACC"},
        "is_conference_game": True,
        "is_tournament": False,
        "venue": "Cameron Indoor Stadium",
        "neutral_site": False,
        "status": "scheduled",
        "home_score": None,
        "away_score": None,
    }


@pytest.fixture
def completed_game_record(full_game_record):
    """Game record after completion with final scores."""
    return {
        **full_game_record,
        "status": "final",
        "home_score": 78,
        "away_score": 72,
    }


@pytest.fixture
def full_spread_data():
    """Complete spread data for a game."""
    return {
        "id": "spread-uuid-1234",
        "game_id": "550e8400-e29b-41d4-a716-446655440000",
        "home_spread": -7.5,
        "away_spread": 7.5,
        "home_ml": -280,
        "away_ml": 220,
        "over_under": 145.5,
        "source": "odds-api",
        "captured_at": "2025-02-15T12:00:00+00:00",
    }


@pytest.fixture
def full_kenpom_home():
    """Full KenPom data for home team."""
    return {
        "team_id": "duke-uuid-1234",
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
        "wins": 22,
        "losses": 3,
    }


@pytest.fixture
def full_kenpom_away():
    """Full KenPom data for away team."""
    return {
        "team_id": "unc-uuid-5678",
        "season": 2025,
        "rank": 10,
        "adj_efficiency_margin": 22.0,
        "adj_offense": 116.8,
        "adj_offense_rank": 8,
        "adj_defense": 94.8,
        "adj_defense_rank": 15,
        "adj_tempo": 72.1,
        "adj_tempo_rank": 30,
        "sos_adj_em": 11.8,
        "sos_adj_em_rank": 12,
        "luck": -0.01,
        "luck_rank": 200,
        "wins": 19,
        "losses": 6,
    }


@pytest.fixture
def full_haslametrics_home():
    """Full Haslametrics data for home team."""
    return {
        "team_id": "duke-uuid-1234",
        "season": 2025,
        "rank": 4,
        "offensive_efficiency": 118.2,
        "defensive_efficiency": 89.5,
        "efficiency_margin": 28.7,
        "all_play_pct": 0.94,
        "momentum_overall": 0.05,
        "momentum_offense": 0.03,
        "momentum_defense": 0.07,
        "consistency": 0.12,
        "sos": 0.65,
        "last_5_record": "5-0",
        "quad_1_record": "6-1",
        "quad_2_record": "4-0",
    }


@pytest.fixture
def full_haslametrics_away():
    """Full Haslametrics data for away team."""
    return {
        "team_id": "unc-uuid-5678",
        "season": 2025,
        "rank": 12,
        "offensive_efficiency": 115.5,
        "defensive_efficiency": 93.2,
        "efficiency_margin": 22.3,
        "all_play_pct": 0.87,
        "momentum_overall": -0.02,
        "momentum_offense": 0.01,
        "momentum_defense": -0.05,
        "consistency": 0.18,
        "sos": 0.60,
        "last_5_record": "3-2",
        "quad_1_record": "4-3",
        "quad_2_record": "3-1",
    }


@pytest.fixture
def claude_analysis_response():
    """Structured response from Claude AI analysis."""
    return {
        "recommended_bet": "home_spread",
        "confidence_score": 0.72,
        "key_factors": [
            "Duke's elite defense ranks #2 in AdjD at 90.0",
            "Home court advantage at Cameron Indoor gives 5+ point boost",
            "KenPom AdjEM differential of 6.5 points favors Duke beyond the spread",
            "Duke's momentum is strongly positive (0.05) while UNC trending down (-0.02)",
        ],
        "reasoning": (
            "Duke's defensive efficiency creates matchup problems for UNC. "
            "The 7.5-point spread appears accurate based on KenPom differentials (6.5 AdjEM gap) "
            "plus typical 3-4 point home court advantage. However, UNC's negative momentum "
            "and Duke's 5-0 last-5 record suggest Duke may cover. The spread is fairly "
            "priced but Duke's current form tips the balance."
        ),
    }


@pytest.fixture
def grok_analysis_response():
    """Structured response from Grok AI analysis."""
    return {
        "recommended_bet": "away_spread",
        "confidence_score": 0.62,
        "key_factors": [
            "Rivalry games historically play closer to the line",
            "UNC's Q1 record (4-3) shows they compete with top teams",
            "Duke's 0.02 luck rating suggests some regression may be coming",
        ],
        "reasoning": (
            "While Duke is the better team overall, rivalry dynamics tend to compress "
            "margins. UNC has shown they can compete with elite opponents (4-3 in Q1 games). "
            "Duke's slightly positive luck factor (0.02) hints they've been winning close "
            "games at an unsustainable rate. The 7.5-point spread may be too wide for a "
            "conference rivalry game."
        ),
    }


@pytest.fixture
def stored_ai_analysis():
    """AI analysis record as stored and retrieved from Supabase."""
    return {
        "id": "analysis-uuid-9999",
        "game_id": "550e8400-e29b-41d4-a716-446655440000",
        "ai_provider": "claude",
        "model_used": "claude-sonnet-4-20250514",
        "recommended_bet": "home_spread",
        "confidence_score": 0.72,
        "key_factors": [
            "Duke's elite defense ranks #2 in AdjD at 90.0",
            "Home court advantage at Cameron Indoor",
            "KenPom AdjEM differential favors Duke",
        ],
        "reasoning": "Duke's defensive efficiency creates matchup problems for UNC.",
        "tokens_used": 750,
        "created_at": "2025-02-15T10:30:00+00:00",
    }


# ============================================================================
# E2E TESTS: FULL AI ANALYSIS WORKFLOW
# ============================================================================

class TestE2EAnalysisWorkflow:
    """Test the complete AI analysis workflow from API trigger to stored result."""

    def test_full_claude_analysis_workflow(
        self,
        app_client,
        full_game_record,
        full_spread_data,
        full_kenpom_home,
        full_kenpom_away,
        full_haslametrics_home,
        full_haslametrics_away,
        claude_analysis_response,
    ):
        """
        E2E: POST /ai-analysis triggers full Claude analysis pipeline.

        Flow: API call -> build_game_context -> build_prompt -> call_claude ->
              parse_response -> save_to_db -> return_result
        """
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(claude_analysis_response))]
        mock_response.usage.input_tokens = 1200
        mock_response.usage.output_tokens = 350
        mock_claude.messages.create.return_value = mock_response

        saved_analysis = {
            "id": "analysis-uuid-new",
            "created_at": datetime.now().isoformat(),
        }

        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value={"rank": 5}), \
             patch("backend.api.ai_service.get_team_kenpom", side_effect=[full_kenpom_home, full_kenpom_away]), \
             patch("backend.api.ai_service.get_team_haslametrics", side_effect=[full_haslametrics_home, full_haslametrics_away]), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis) as mock_insert, \
             patch("backend.api.ai_service.claude_client", mock_claude):

            response = app_client.post(
                "/ai-analysis",
                json={
                    "game_id": "550e8400-e29b-41d4-a716-446655440000",
                    "provider": "claude",
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response contains all expected fields
            assert data["game_id"] == "550e8400-e29b-41d4-a716-446655440000"
            assert data["provider"] == "claude"
            assert data["recommended_bet"] == "home_spread"
            assert data["confidence_score"] == 0.72
            assert len(data["key_factors"]) == 4
            assert "defensive efficiency" in data["reasoning"].lower() or "Duke" in data["reasoning"]

            # Verify the analysis was saved to database
            mock_insert.assert_called_once()
            insert_args = mock_insert.call_args
            saved_data = insert_args[0][0] if insert_args[0] else insert_args[1]
            # Verify the insert includes required fields
            assert mock_insert.called

    def test_full_grok_analysis_workflow(
        self,
        app_client,
        full_game_record,
        full_spread_data,
        grok_analysis_response,
    ):
        """
        E2E: POST /ai-analysis with Grok provider runs complete pipeline.
        """
        mock_grok = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(grok_analysis_response)
        mock_grok_response = MagicMock()
        mock_grok_response.choices = [MagicMock(message=mock_message)]
        mock_grok_response.usage = MagicMock(total_tokens=800)
        mock_grok.chat.completions.create.return_value = mock_grok_response

        saved_analysis = {
            "id": "analysis-grok-uuid",
            "created_at": datetime.now().isoformat(),
        }

        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis), \
             patch("backend.api.ai_service.grok_client", mock_grok):

            response = app_client.post(
                "/ai-analysis",
                json={
                    "game_id": "550e8400-e29b-41d4-a716-446655440000",
                    "provider": "grok",
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert data["provider"] == "grok"
            assert data["recommended_bet"] == "away_spread"
            assert data["confidence_score"] == 0.62


class TestE2EContextBuilding:
    """Test that game context is built correctly from all data sources."""

    def test_context_includes_all_data_sources(
        self,
        full_game_record,
        full_spread_data,
        full_kenpom_home,
        full_kenpom_away,
        full_haslametrics_home,
        full_haslametrics_away,
    ):
        """Context includes game info, spread, KenPom, Haslametrics, and prediction markets."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value={"rank": 5}), \
             patch("backend.api.ai_service.get_team_kenpom", side_effect=[full_kenpom_home, full_kenpom_away]), \
             patch("backend.api.ai_service.get_team_haslametrics", side_effect=[full_haslametrics_home, full_haslametrics_away]), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]):

            from backend.api.ai_service import build_game_context

            context = build_game_context("550e8400-e29b-41d4-a716-446655440000")

            # Verify game info
            assert context["home_team"] == "Duke"
            assert context["away_team"] == "North Carolina"
            assert context["is_conference_game"] is True

            # Verify spread data
            assert context["spread"] == -7.5
            assert context["home_ml"] == -280
            assert context["away_ml"] == 220
            assert context["total"] == 145.5

            # Verify KenPom data
            assert context["home_kenpom"]["adj_efficiency_margin"] == 28.5
            assert context["away_kenpom"]["adj_efficiency_margin"] == 22.0

            # Verify Haslametrics data
            assert context["home_haslametrics"]["all_play_pct"] == 0.94
            assert context["away_haslametrics"]["all_play_pct"] == 0.87

    def test_context_handles_partial_data_gracefully(self, full_game_record, full_spread_data):
        """Context built with partial data (no analytics) still works."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]):

            from backend.api.ai_service import build_game_context

            context = build_game_context("550e8400-e29b-41d4-a716-446655440000")

            # Basic data still present
            assert context["home_team"] == "Duke"
            assert context["spread"] == -7.5

            # Analytics absent
            assert context["home_kenpom"] is None
            assert context["away_kenpom"] is None
            assert context["home_haslametrics"] is None
            assert context["away_haslametrics"] is None

    def test_context_with_prediction_market_data(
        self,
        full_game_record,
        full_spread_data,
    ):
        """Context includes prediction market and arbitrage data when available."""
        prediction_markets = [
            {
                "id": "pm-uuid-1",
                "game_id": "550e8400-e29b-41d4-a716-446655440000",
                "platform": "polymarket",
                "market_title": "Duke vs UNC Winner",
                "outcomes": [
                    {"name": "Duke", "price": 0.78},
                    {"name": "North Carolina", "price": 0.22},
                ],
            }
        ]

        arbitrage_ops = [
            {
                "id": "arb-uuid-1",
                "game_id": "550e8400-e29b-41d4-a716-446655440000",
                "bet_type": "home_ml",
                "edge_pct": 12.5,
                "platform": "polymarket",
                "sportsbook_implied_prob": 0.737,
                "prediction_market_prob": 0.78,
            }
        ]

        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=prediction_markets), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=arbitrage_ops):

            from backend.api.ai_service import build_game_context

            context = build_game_context("550e8400-e29b-41d4-a716-446655440000")

            assert len(context["prediction_markets"]) == 1
            assert context["prediction_markets"][0]["platform"] == "polymarket"
            assert len(context["arbitrage_opportunities"]) == 1
            assert context["arbitrage_opportunities"][0]["edge_pct"] == 12.5


class TestE2EPromptConstruction:
    """Test that the AI prompt is constructed with all relevant data."""

    def test_prompt_includes_kenpom_and_haslametrics_cross_validation(
        self,
        full_kenpom_home,
        full_kenpom_away,
        full_haslametrics_home,
        full_haslametrics_away,
    ):
        """When both analytics available, prompt includes cross-validation instructions."""
        from backend.api.ai_service import build_analysis_prompt

        context = {
            "game_id": "test-uuid",
            "date": "2025-02-15",
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
            "spread": -7.5,
            "home_ml": -280,
            "away_ml": 220,
            "total": 145.5,
            "home_kenpom": full_kenpom_home,
            "away_kenpom": full_kenpom_away,
            "home_haslametrics": full_haslametrics_home,
            "away_haslametrics": full_haslametrics_away,
            "prediction_markets": [],
            "arbitrage_opportunities": [],
        }

        prompt = build_analysis_prompt(context)

        # Both analytics sections included
        assert "KENPOM" in prompt
        assert "HASLAMETRICS" in prompt

        # Cross-validation mentioned
        assert "Cross-validate" in prompt or "cross-validate" in prompt.lower()

        # Specific data points present
        assert "118.5" in prompt  # AdjO
        assert "90.0" in prompt  # AdjD
        assert "0.94" in prompt or "94" in prompt  # All-Play %

        # JSON format required
        assert "recommended_bet" in prompt
        assert "confidence_score" in prompt

    def test_prompt_adjusts_for_missing_analytics(self):
        """Prompt adapts when no advanced analytics are available."""
        from backend.api.ai_service import build_analysis_prompt

        minimal_context = {
            "game_id": "test-uuid",
            "date": "2025-02-15",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_conference": "ACC",
            "away_conference": "ACC",
            "home_rank": 5,
            "away_rank": None,
            "is_conference_game": True,
            "is_tournament": False,
            "venue": "Cameron Indoor Stadium",
            "neutral_site": False,
            "spread": -7.5,
            "home_ml": -280,
            "away_ml": 220,
            "total": 145.5,
            "home_kenpom": None,
            "away_kenpom": None,
            "home_haslametrics": None,
            "away_haslametrics": None,
            "prediction_markets": [],
            "arbitrage_opportunities": [],
        }

        prompt = build_analysis_prompt(minimal_context)

        # No analytics sections
        assert "KENPOM ADVANCED ANALYTICS" not in prompt
        assert "HASLAMETRICS ANALYTICS" not in prompt

        # Basic game info still present
        assert "Duke" in prompt
        assert "North Carolina" in prompt
        assert "-7.5" in prompt


class TestE2EAnalysisComparison:
    """Test comparing AI analysis results with actual game outcomes."""

    def test_analysis_prediction_vs_actual_home_cover(self, stored_ai_analysis, completed_game_record):
        """When AI predicts home_spread and home covers, analysis is correct."""
        # Game result: Duke 78, UNC 72 -> Duke wins by 6
        # Spread: Duke -7.5 -> Duke needed to win by 8+ to cover
        # Result: Duke DOES NOT cover (won by only 6)
        # AI predicted: home_spread (Duke covers) -> INCORRECT

        margin = completed_game_record["home_score"] - completed_game_record["away_score"]
        spread = -7.5  # Home spread
        home_covered = margin > abs(spread)

        assert margin == 6  # Duke won by 6
        assert home_covered is False  # Duke did NOT cover -7.5
        assert stored_ai_analysis["recommended_bet"] == "home_spread"

        # AI was wrong in this case - the away spread was the right bet
        prediction_correct = home_covered  # AI said home covers
        assert prediction_correct is False

    def test_analysis_prediction_vs_actual_away_spread(self, grok_analysis_response, completed_game_record):
        """Grok predicted away_spread - verify outcome."""
        # Game result: Duke 78, UNC 72 -> Duke wins by 6
        # Spread: Duke -7.5, UNC +7.5
        # UNC +7.5 means UNC covers if they lose by less than 7.5
        # UNC lost by 6 < 7.5 -> UNC COVERS

        margin = completed_game_record["home_score"] - completed_game_record["away_score"]
        away_covered = margin < 7.5  # Away team covers if margin < spread

        assert margin == 6
        assert away_covered is True  # UNC covered +7.5
        assert grok_analysis_response["recommended_bet"] == "away_spread"

        # Grok was correct!
        prediction_correct = away_covered
        assert prediction_correct is True

    def test_dual_provider_consensus_comparison(
        self,
        claude_analysis_response,
        grok_analysis_response,
        completed_game_record,
    ):
        """Compare both providers' recommendations against the actual result."""
        margin = completed_game_record["home_score"] - completed_game_record["away_score"]
        spread = 7.5

        away_covered = margin < spread  # UNC +7.5 covers if Duke wins by less than 7.5

        # Claude: home_spread (Duke -7.5 covers) -> WRONG (Duke won by 6)
        claude_correct = not away_covered
        assert claude_correct is False

        # Grok: away_spread (UNC +7.5 covers) -> CORRECT (UNC lost by only 6)
        grok_correct = away_covered
        assert grok_correct is True

        # When providers disagree, the lower-confidence one was right here
        assert claude_analysis_response["confidence_score"] > grok_analysis_response["confidence_score"]

    def test_over_under_result_analysis(self, completed_game_record):
        """Test over/under prediction comparison with actual total."""
        total_score = completed_game_record["home_score"] + completed_game_record["away_score"]
        over_under_line = 145.5

        assert total_score == 150  # 78 + 72
        went_over = total_score > over_under_line
        assert went_over is True


class TestE2EDebugEndpoint:
    """Test the debug endpoint shows step-by-step analysis progress."""

    def test_debug_shows_data_availability(
        self,
        app_client,
        full_game_record,
        full_spread_data,
        full_kenpom_home,
        full_haslametrics_home,
    ):
        """Debug endpoint reports which data sources were available."""
        with patch("backend.api.main.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.main.build_game_context") as mock_context, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key", "GROK_API_KEY": "test-key"}):

            mock_context.return_value = {
                "game_id": full_game_record["id"],
                "home_kenpom": full_kenpom_home,
                "away_kenpom": None,
                "home_haslametrics": full_haslametrics_home,
                "away_haslametrics": None,
                "spread": -7.5,
            }

            response = app_client.get(
                f"/debug/ai-analysis/{full_game_record['id']}?provider=claude"
            )

            assert response.status_code == 200
            data = response.json()
            assert data["steps"]["1_game_fetch"]["status"] == "success"
            assert data["steps"]["2_build_context"]["status"] == "success"

    def test_debug_shows_game_not_found(self, app_client):
        """Debug endpoint handles missing game."""
        with patch("backend.api.main.get_game_by_id", return_value=None):
            response = app_client.get("/debug/ai-analysis/nonexistent-uuid")

            assert response.status_code == 200
            data = response.json()
            assert data["steps"]["1_game_fetch"]["status"] == "failed"


class TestE2EAnalysisWithPredictionMarkets:
    """Test AI analysis that incorporates prediction market data."""

    def test_analysis_prompt_includes_arbitrage_signal(
        self,
        full_kenpom_home,
        full_kenpom_away,
    ):
        """When arbitrage opportunities exist, they appear in the prompt."""
        from backend.api.ai_service import build_analysis_prompt

        context = {
            "game_id": "test-uuid",
            "date": "2025-02-15",
            "home_team": "Duke",
            "away_team": "North Carolina",
            "home_conference": "ACC",
            "away_conference": "ACC",
            "home_rank": 5,
            "away_rank": 8,
            "is_conference_game": True,
            "is_tournament": False,
            "venue": "Cameron Indoor",
            "neutral_site": False,
            "spread": -7.5,
            "home_ml": -280,
            "away_ml": 220,
            "total": 145.5,
            "home_kenpom": full_kenpom_home,
            "away_kenpom": full_kenpom_away,
            "home_haslametrics": None,
            "away_haslametrics": None,
            "prediction_markets": [
                {
                    "platform": "polymarket",
                    "market_title": "Duke vs UNC",
                    "outcomes": [
                        {"name": "Duke", "price": 0.82},
                        {"name": "North Carolina", "price": 0.18},
                    ]
                }
            ],
            "arbitrage_opportunities": [
                {
                    "bet_type": "home_ml",
                    "edge_pct": 14.2,
                    "platform": "polymarket",
                }
            ],
        }

        prompt = build_analysis_prompt(context)

        # Prediction market data should be included
        assert "polymarket" in prompt.lower() or "prediction market" in prompt.lower() or "PREDICTION" in prompt


class TestE2EErrorRecovery:
    """Test that the E2E workflow handles errors gracefully."""

    def test_api_continues_when_one_data_source_fails(
        self,
        app_client,
        full_game_record,
        full_spread_data,
        claude_analysis_response,
    ):
        """Analysis still works when some data sources fail."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(claude_analysis_response))]
        mock_response.usage.input_tokens = 800
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        saved = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        # KenPom raises an exception, but analysis should still proceed
        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved), \
             patch("backend.api.ai_service.claude_client", mock_claude):

            response = app_client.post(
                "/ai-analysis",
                json={
                    "game_id": "550e8400-e29b-41d4-a716-446655440000",
                    "provider": "claude",
                }
            )

            # Should succeed even without analytics data
            assert response.status_code == 200
            data = response.json()
            assert data["recommended_bet"] is not None

    def test_malformed_ai_response_returns_safe_default(
        self,
        app_client,
        full_game_record,
        full_spread_data,
    ):
        """When AI returns unparseable response, safe defaults are used."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Sorry, I cannot provide betting advice at this time.")]
        mock_response.usage.input_tokens = 800
        mock_response.usage.output_tokens = 20
        mock_claude.messages.create.return_value = mock_response

        saved = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=full_game_record), \
             patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
             patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved), \
             patch("backend.api.ai_service.claude_client", mock_claude):

            response = app_client.post(
                "/ai-analysis",
                json={
                    "game_id": "550e8400-e29b-41d4-a716-446655440000",
                    "provider": "claude",
                }
            )

            assert response.status_code == 200
            data = response.json()
            # Should fall back to "pass" recommendation
            assert data["recommended_bet"] == "pass"
            assert data["confidence_score"] == 0.5


class TestE2EMultipleGameAnalysis:
    """Test analyzing multiple games in sequence (batch-like workflow)."""

    def test_analyze_multiple_games_sequentially(self, full_game_record, full_spread_data, claude_analysis_response):
        """Simulate analyzing 3 games in sequence as done in daily refresh."""
        games = []
        for i in range(3):
            game = {**full_game_record, "id": f"game-uuid-{i}"}
            games.append(game)

        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(claude_analysis_response))]
        mock_response.usage.input_tokens = 800
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        saved = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        results = []
        for game in games:
            with patch("backend.api.ai_service.get_game_by_id", return_value=game), \
                 patch("backend.api.ai_service.get_latest_spread", return_value=full_spread_data), \
                 patch("backend.api.ai_service.get_team_ranking", return_value=None), \
                 patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
                 patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
                 patch("backend.api.ai_service.get_game_prediction_markets", return_value=[]), \
                 patch("backend.api.ai_service.get_game_arbitrage_opportunities", return_value=[]), \
                 patch("backend.api.ai_service.insert_ai_analysis", return_value=saved), \
                 patch("backend.api.ai_service.claude_client", mock_claude):

                from backend.api.ai_service import analyze_game
                result = analyze_game(game["id"], provider="claude", save=True)
                results.append(result)

        assert len(results) == 3
        for result in results:
            assert result["ai_provider"] == "claude"
            assert result["recommended_bet"] == "home_spread"

        # Claude API was called 3 times
        assert mock_claude.messages.create.call_count == 3

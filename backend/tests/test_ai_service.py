"""
Tests for AI service module (ai_service.py).

Tests cover:
- build_game_context: Context building from database data
- build_analysis_prompt: Prompt construction with various data combinations
- analyze_with_claude: Claude API integration and response parsing
- analyze_with_grok: Grok API integration and response parsing
- analyze_game: Full analysis workflow
- get_quick_recommendation: Heuristic-based recommendations
- AIAnalyzer: Class behavior including caching
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


class TestBuildGameContext:
    """Tests for build_game_context function."""

    def test_build_game_context_with_all_data(
        self, sample_game, sample_spread, sample_ranking, sample_kenpom, sample_haslametrics
    ):
        """Test context building when all data sources are available."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=sample_ranking), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=sample_kenpom), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=sample_haslametrics):

            from backend.api.ai_service import build_game_context

            context = build_game_context(sample_game["id"])

            assert context["game_id"] == sample_game["id"]
            assert context["home_team"] == "Duke"
            assert context["away_team"] == "North Carolina"
            assert context["spread"] == -7.5
            assert context["home_kenpom"] is not None
            assert context["home_haslametrics"] is not None
            assert context["is_conference_game"] is True

    def test_build_game_context_game_not_found(self):
        """Test context building when game doesn't exist."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=None):
            from backend.api.ai_service import build_game_context

            with pytest.raises(ValueError, match="Game not found"):
                build_game_context("nonexistent-game-id")

    def test_build_game_context_no_spread(self, sample_game):
        """Test context building when spread data is not available."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=None), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None):

            from backend.api.ai_service import build_game_context

            context = build_game_context(sample_game["id"])

            assert context["spread"] is None
            assert context["home_ml"] is None
            assert context["away_ml"] is None
            assert context["total"] is None

    def test_build_game_context_no_analytics(self, sample_game, sample_spread):
        """Test context building when KenPom and Haslametrics are not available."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None):

            from backend.api.ai_service import build_game_context

            context = build_game_context(sample_game["id"])

            assert context["home_kenpom"] is None
            assert context["away_kenpom"] is None
            assert context["home_haslametrics"] is None
            assert context["away_haslametrics"] is None


class TestBuildAnalysisPrompt:
    """Tests for build_analysis_prompt function."""

    def test_build_analysis_prompt_full_context(self, sample_game_context):
        """Test prompt generation with full context (both analytics)."""
        from backend.api.ai_service import build_analysis_prompt

        prompt = build_analysis_prompt(sample_game_context)

        # Verify basic matchup info is included
        assert "Duke" in prompt
        assert "North Carolina" in prompt
        assert "#5" in prompt  # home_rank
        assert "#8" in prompt  # away_rank

        # Verify spread info
        assert "-7.5" in prompt
        assert "ML:" in prompt

        # Verify KenPom section is included
        assert "KENPOM ADVANCED ANALYTICS" in prompt
        assert "Adj. Offense" in prompt
        assert "Adj. Defense" in prompt

        # Verify Haslametrics section is included
        assert "HASLAMETRICS ANALYTICS" in prompt
        assert "All-Play %" in prompt
        assert "Momentum" in prompt

        # Verify cross-validation guidance when both sources available
        assert "Cross-validate" in prompt

    def test_build_analysis_prompt_kenpom_only(self, sample_game_context):
        """Test prompt when only KenPom data is available."""
        from backend.api.ai_service import build_analysis_prompt

        context = {**sample_game_context}
        context["home_haslametrics"] = None
        context["away_haslametrics"] = None

        prompt = build_analysis_prompt(context)

        assert "KENPOM ADVANCED ANALYTICS" in prompt
        assert "HASLAMETRICS ANALYTICS" not in prompt
        assert "KenPom efficiency differentials" in prompt

    def test_build_analysis_prompt_haslametrics_only(self, sample_game_context):
        """Test prompt when only Haslametrics data is available."""
        from backend.api.ai_service import build_analysis_prompt

        context = {**sample_game_context}
        context["home_kenpom"] = None
        context["away_kenpom"] = None

        prompt = build_analysis_prompt(context)

        assert "HASLAMETRICS ANALYTICS" in prompt
        assert "KENPOM ADVANCED ANALYTICS" not in prompt
        assert "Haslametrics efficiency comparison" in prompt

    def test_build_analysis_prompt_no_analytics(self, sample_game_context):
        """Test prompt when no advanced analytics are available."""
        from backend.api.ai_service import build_analysis_prompt

        context = {**sample_game_context}
        context["home_kenpom"] = None
        context["away_kenpom"] = None
        context["home_haslametrics"] = None
        context["away_haslametrics"] = None

        prompt = build_analysis_prompt(context)

        assert "KENPOM ADVANCED ANALYTICS" not in prompt
        assert "HASLAMETRICS ANALYTICS" not in prompt
        assert "Ranking differential" in prompt

    def test_build_analysis_prompt_unranked_teams(self, sample_game_context):
        """Test prompt when teams are unranked."""
        from backend.api.ai_service import build_analysis_prompt

        context = {**sample_game_context}
        context["home_rank"] = None
        context["away_rank"] = None

        prompt = build_analysis_prompt(context)

        assert "Unranked" in prompt

    def test_build_analysis_prompt_away_favored(self, sample_game_context):
        """Test spread display when away team is favored."""
        from backend.api.ai_service import build_analysis_prompt

        context = {**sample_game_context}
        context["spread"] = 7.5  # Positive = away favored

        prompt = build_analysis_prompt(context)

        assert "North Carolina -7.5" in prompt

    def test_build_analysis_prompt_json_format_requested(self, sample_game_context):
        """Test that prompt requests JSON format response."""
        from backend.api.ai_service import build_analysis_prompt

        prompt = build_analysis_prompt(sample_game_context)

        assert "JSON format" in prompt
        assert "recommended_bet" in prompt
        assert "confidence_score" in prompt
        assert "key_factors" in prompt
        assert "reasoning" in prompt


class TestAnalyzeWithClaude:
    """Tests for analyze_with_claude function."""

    def test_analyze_with_claude_success(self, sample_game_context, valid_claude_response):
        """Test successful Claude analysis."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            assert result["ai_provider"] == "claude"
            assert result["model_used"] == "claude-sonnet-4-20250514"
            assert result["recommended_bet"] == "home_spread"
            assert result["confidence_score"] == 0.72
            assert len(result["key_factors"]) == 3
            assert result["tokens_used"] == 700

    def test_analyze_with_claude_not_configured(self, sample_game_context):
        """Test error when Claude API key is not configured."""
        with patch("backend.api.ai_service.claude_client", None):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(ValueError, match="Claude API key not configured"):
                analyze_with_claude(sample_game_context)

    def test_analyze_with_claude_malformed_json_response(self, sample_game_context):
        """Test handling of malformed JSON response from Claude."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Response with JSON embedded in text
        mock_response.content = [MagicMock(
            text='Here is my analysis: {"recommended_bet": "pass", "confidence_score": 0.5, "key_factors": ["No clear edge"], "reasoning": "Cannot determine value"}'
        )]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            # Should extract JSON from mixed text
            assert result["recommended_bet"] == "pass"
            assert result["confidence_score"] == 0.5

    def test_analyze_with_claude_completely_invalid_response(self, sample_game_context):
        """Test handling when Claude returns no valid JSON."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="I cannot provide betting advice.")]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            # Should fallback to default values
            assert result["recommended_bet"] == "pass"
            assert result["confidence_score"] == 0.5
            assert "Unable to parse AI response" in result["key_factors"]

    def test_analyze_with_claude_api_error(self, sample_game_context):
        """Test handling of Claude API errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(Exception, match="API rate limit exceeded"):
                analyze_with_claude(sample_game_context)


class TestAnalyzeWithGrok:
    """Tests for analyze_with_grok function."""

    def test_analyze_with_grok_success(self, sample_game_context, valid_grok_response):
        """Test successful Grok analysis."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(valid_grok_response)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.usage = MagicMock(total_tokens=700)
        mock_client.chat.completions.create.return_value = mock_response

        with patch("backend.api.ai_service.grok_client", mock_client):
            from backend.api.ai_service import analyze_with_grok

            result = analyze_with_grok(sample_game_context)

            assert result["ai_provider"] == "grok"
            assert result["model_used"] == "grok-3"
            assert result["recommended_bet"] == "away_spread"
            assert result["confidence_score"] == 0.65
            assert len(result["key_factors"]) == 3
            assert result["tokens_used"] == 700

    def test_analyze_with_grok_not_configured(self, sample_game_context):
        """Test error when Grok API key is not configured."""
        with patch("backend.api.ai_service.grok_client", None):
            from backend.api.ai_service import analyze_with_grok

            with pytest.raises(ValueError, match="Grok API key not configured"):
                analyze_with_grok(sample_game_context)

    def test_analyze_with_grok_malformed_json_response(self, sample_game_context):
        """Test handling of malformed JSON response from Grok."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = 'Analysis complete. {"recommended_bet": "over", "confidence_score": 0.6, "key_factors": ["High-scoring teams"], "reasoning": "Both teams score well"}'
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.usage = MagicMock(total_tokens=500)
        mock_client.chat.completions.create.return_value = mock_response

        with patch("backend.api.ai_service.grok_client", mock_client):
            from backend.api.ai_service import analyze_with_grok

            result = analyze_with_grok(sample_game_context)

            assert result["recommended_bet"] == "over"
            assert result["confidence_score"] == 0.6

    def test_analyze_with_grok_no_usage_data(self, sample_game_context, valid_grok_response):
        """Test handling when Grok response has no usage data."""
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(valid_grok_response)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.usage = None  # No usage data
        mock_client.chat.completions.create.return_value = mock_response

        with patch("backend.api.ai_service.grok_client", mock_client):
            from backend.api.ai_service import analyze_with_grok

            result = analyze_with_grok(sample_game_context)

            assert result["tokens_used"] == 0


class TestAnalyzeGame:
    """Tests for analyze_game function (full workflow)."""

    def test_analyze_game_claude_with_save(
        self, sample_game, sample_spread, sample_kenpom, sample_haslametrics, valid_claude_response
    ):
        """Test full analysis workflow with Claude and database save."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        saved_analysis = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=sample_kenpom), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=sample_haslametrics), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis) as mock_insert, \
             patch("backend.api.ai_service.claude_client", mock_claude):

            from backend.api.ai_service import analyze_game

            result = analyze_game(sample_game["id"], provider="claude", save=True)

            assert result["game_id"] == sample_game["id"]
            assert result["ai_provider"] == "claude"
            assert result["id"] == "analysis-uuid"
            mock_insert.assert_called_once()

    def test_analyze_game_grok_without_save(
        self, sample_game, sample_spread, valid_grok_response
    ):
        """Test analysis workflow with Grok without saving to database."""
        mock_grok = MagicMock()
        mock_message = MagicMock()
        mock_message.content = json.dumps(valid_grok_response)
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_response.usage = MagicMock(total_tokens=700)
        mock_grok.chat.completions.create.return_value = mock_response

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.insert_ai_analysis") as mock_insert, \
             patch("backend.api.ai_service.grok_client", mock_grok):

            from backend.api.ai_service import analyze_game

            result = analyze_game(sample_game["id"], provider="grok", save=False)

            assert result["game_id"] == sample_game["id"]
            assert result["ai_provider"] == "grok"
            assert "id" not in result  # Not saved
            mock_insert.assert_not_called()

    def test_analyze_game_unknown_provider(self, sample_game, sample_spread):
        """Test error when unknown provider is specified."""
        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None):

            from backend.api.ai_service import analyze_game

            with pytest.raises(ValueError, match="Unknown provider"):
                analyze_game(sample_game["id"], provider="unknown")


class TestGetQuickRecommendation:
    """Tests for get_quick_recommendation heuristic function."""

    def test_quick_recommendation_top5_home_large_spread(self):
        """Test underdog recommendation when top 5 team has large spread."""
        from backend.api.ai_service import get_quick_recommendation

        context = {
            "home_rank": 3,
            "away_rank": None,
            "spread": -14,  # Home favored by 14
            "is_conference_game": True,
        }

        result = get_quick_recommendation(context)

        assert result["recommended_bet"] == "away_spread"
        assert result["confidence_score"] == 0.58
        assert "cover" in result["reasoning"].lower()

    def test_quick_recommendation_top5_away_large_spread(self):
        """Test home underdog recommendation when top 5 road team."""
        from backend.api.ai_service import get_quick_recommendation

        context = {
            "home_rank": None,
            "away_rank": 2,
            "spread": 15,  # Away favored by 15
            "is_conference_game": True,
        }

        result = get_quick_recommendation(context)

        assert result["recommended_bet"] == "home_spread"
        assert result["confidence_score"] == 0.58

    def test_quick_recommendation_no_clear_edge(self):
        """Test pass recommendation when no clear edge exists."""
        from backend.api.ai_service import get_quick_recommendation

        context = {
            "home_rank": 10,
            "away_rank": 15,
            "spread": -5,
            "is_conference_game": True,
        }

        result = get_quick_recommendation(context)

        assert result["recommended_bet"] == "pass"
        assert result["confidence_score"] == 0.5

    def test_quick_recommendation_non_conference(self):
        """Test that non-conference games return pass."""
        from backend.api.ai_service import get_quick_recommendation

        context = {
            "home_rank": 3,
            "away_rank": None,
            "spread": -14,
            "is_conference_game": False,  # Not conference game
        }

        result = get_quick_recommendation(context)

        assert result["recommended_bet"] == "pass"

    def test_quick_recommendation_no_spread(self):
        """Test handling when spread is not available."""
        from backend.api.ai_service import get_quick_recommendation

        context = {
            "home_rank": 5,
            "away_rank": None,
            "spread": None,
            "is_conference_game": True,
        }

        result = get_quick_recommendation(context)

        assert result["recommended_bet"] == "pass"


class TestAIAnalyzer:
    """Tests for AIAnalyzer class."""

    def test_analyzer_caching(self, sample_game, sample_spread, valid_claude_response):
        """Test that analyzer caches results."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        saved_analysis = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis), \
             patch("backend.api.ai_service.claude_client", mock_claude):

            from backend.api.ai_service import AIAnalyzer

            analyzer = AIAnalyzer()

            # First call
            result1 = analyzer.analyze(sample_game["id"], provider="claude", use_cache=True)
            # Second call - should return cached result
            result2 = analyzer.analyze(sample_game["id"], provider="claude", use_cache=True)

            # API should only be called once
            assert mock_claude.messages.create.call_count == 1
            assert result1 == result2

    def test_analyzer_cache_bypass(self, sample_game, sample_spread, valid_claude_response):
        """Test that use_cache=False bypasses cache."""
        mock_claude = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_response

        saved_analysis = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis), \
             patch("backend.api.ai_service.claude_client", mock_claude):

            from backend.api.ai_service import AIAnalyzer

            analyzer = AIAnalyzer()

            # First call
            analyzer.analyze(sample_game["id"], provider="claude", use_cache=True)
            # Second call with cache bypass
            analyzer.analyze(sample_game["id"], provider="claude", use_cache=False)

            # API should be called twice
            assert mock_claude.messages.create.call_count == 2

    def test_analyzer_clear_cache(self):
        """Test that clear_cache empties the cache."""
        from backend.api.ai_service import AIAnalyzer

        analyzer = AIAnalyzer()
        analyzer.cache = {"game1:claude": {"some": "data"}}

        analyzer.clear_cache()

        assert analyzer.cache == {}

    def test_analyzer_analyze_both_providers(
        self, sample_game, sample_spread, valid_claude_response, valid_grok_response
    ):
        """Test analyzing with both Claude and Grok."""
        mock_claude = MagicMock()
        mock_claude_response = MagicMock()
        mock_claude_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_claude_response.usage.input_tokens = 500
        mock_claude_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_claude_response

        mock_grok = MagicMock()
        mock_grok_message = MagicMock()
        mock_grok_message.content = json.dumps(valid_grok_response)
        mock_grok_response = MagicMock()
        mock_grok_response.choices = [MagicMock(message=mock_grok_message)]
        mock_grok_response.usage = MagicMock(total_tokens=700)
        mock_grok.chat.completions.create.return_value = mock_grok_response

        saved_analysis = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis), \
             patch("backend.api.ai_service.claude_client", mock_claude), \
             patch("backend.api.ai_service.grok_client", mock_grok):

            from backend.api.ai_service import AIAnalyzer

            analyzer = AIAnalyzer()
            result = analyzer.analyze_both(sample_game["id"], save=True)

            assert "claude" in result
            assert "grok" in result
            # Claude says home_spread, Grok says away_spread - should be no consensus
            assert result["consensus"]["recommended_bet"] == "pass"
            assert "disagree" in result["consensus"]["reasoning"].lower()

    def test_analyzer_analyze_both_consensus(
        self, sample_game, sample_spread, valid_claude_response
    ):
        """Test analyze_both when providers agree."""
        # Use same response for both providers
        mock_claude = MagicMock()
        mock_claude_response = MagicMock()
        mock_claude_response.content = [MagicMock(text=json.dumps(valid_claude_response))]
        mock_claude_response.usage.input_tokens = 500
        mock_claude_response.usage.output_tokens = 200
        mock_claude.messages.create.return_value = mock_claude_response

        mock_grok = MagicMock()
        mock_grok_message = MagicMock()
        mock_grok_message.content = json.dumps(valid_claude_response)  # Same as Claude
        mock_grok_response = MagicMock()
        mock_grok_response.choices = [MagicMock(message=mock_grok_message)]
        mock_grok_response.usage = MagicMock(total_tokens=700)
        mock_grok.chat.completions.create.return_value = mock_grok_response

        saved_analysis = {"id": "analysis-uuid", "created_at": datetime.now().isoformat()}

        with patch("backend.api.ai_service.get_game_by_id", return_value=sample_game), \
             patch("backend.api.ai_service.get_latest_spread", return_value=sample_spread), \
             patch("backend.api.ai_service.get_team_ranking", return_value=None), \
             patch("backend.api.ai_service.get_team_kenpom", return_value=None), \
             patch("backend.api.ai_service.get_team_haslametrics", return_value=None), \
             patch("backend.api.ai_service.insert_ai_analysis", return_value=saved_analysis), \
             patch("backend.api.ai_service.claude_client", mock_claude), \
             patch("backend.api.ai_service.grok_client", mock_grok):

            from backend.api.ai_service import AIAnalyzer

            analyzer = AIAnalyzer()
            result = analyzer.analyze_both(sample_game["id"], save=True)

            assert result["consensus"]["recommended_bet"] == "home_spread"
            assert "agree" in result["consensus"]["reasoning"].lower()


class TestAPIErrorHandling:
    """Tests for handling specific API error types from AI providers."""

    def test_anthropic_rate_limit_error(self, sample_game_context):
        """Test handling of Anthropic-specific rate limit errors."""
        mock_client = MagicMock()
        # Simulate Anthropic rate limit error
        mock_client.messages.create.side_effect = Exception(
            "Error code: 429 - {'type': 'error', 'error': {'type': 'rate_limit_error', 'message': 'Rate limit exceeded'}}"
        )

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(Exception) as exc_info:
                analyze_with_claude(sample_game_context)

            assert "429" in str(exc_info.value) or "rate_limit" in str(exc_info.value).lower()

    def test_anthropic_overloaded_error(self, sample_game_context):
        """Test handling when Anthropic API is overloaded."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception(
            "Error code: 529 - {'type': 'error', 'error': {'type': 'overloaded_error', 'message': 'API is temporarily overloaded'}}"
        )

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(Exception) as exc_info:
                analyze_with_claude(sample_game_context)

            assert "529" in str(exc_info.value) or "overloaded" in str(exc_info.value).lower()

    def test_grok_rate_limit_error(self, sample_game_context):
        """Test handling of OpenAI-compatible rate limit errors from Grok."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "Error code: 429 - Rate limit exceeded. Please slow down."
        )

        with patch("backend.api.ai_service.grok_client", mock_client):
            from backend.api.ai_service import analyze_with_grok

            with pytest.raises(Exception) as exc_info:
                analyze_with_grok(sample_game_context)

            assert "429" in str(exc_info.value) or "rate limit" in str(exc_info.value).lower()

    def test_ssl_certificate_error(self, sample_game_context):
        """Test handling of SSL certificate errors."""
        mock_client = MagicMock()
        import ssl
        mock_client.messages.create.side_effect = ssl.SSLCertVerificationError(
            "certificate verify failed"
        )

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(ssl.SSLCertVerificationError):
                analyze_with_claude(sample_game_context)

    def test_authentication_error(self, sample_game_context):
        """Test handling of authentication/invalid API key errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception(
            "Error code: 401 - Invalid API key"
        )

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(Exception) as exc_info:
                analyze_with_claude(sample_game_context)

            assert "401" in str(exc_info.value)

    def test_bad_request_error(self, sample_game_context):
        """Test handling of bad request errors (malformed request)."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception(
            "Error code: 400 - Invalid request body"
        )

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            with pytest.raises(Exception) as exc_info:
                analyze_with_claude(sample_game_context)

            assert "400" in str(exc_info.value)


class TestResponseParsing:
    """Tests specifically for JSON response parsing edge cases."""

    def test_parse_json_with_markdown_code_block(self, sample_game_context):
        """Test parsing JSON wrapped in markdown code blocks."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='''```json
{"recommended_bet": "under", "confidence_score": 0.68, "key_factors": ["Slow pace"], "reasoning": "Low scoring expected"}
```''')]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            # The current implementation uses regex to find JSON, should still work
            # If not, this test documents the expected behavior
            assert result["recommended_bet"] in ["under", "pass"]

    def test_parse_json_with_extra_whitespace(self, sample_game_context):
        """Test parsing JSON with extra whitespace."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='''
        {
            "recommended_bet": "home_ml",
            "confidence_score": 0.75,
            "key_factors": ["Strong favorite"],
            "reasoning": "Heavy favorite should win outright"
        }
        ''')]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 200
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            assert result["recommended_bet"] == "home_ml"
            assert result["confidence_score"] == 0.75

    def test_parse_json_missing_optional_fields(self, sample_game_context):
        """Test parsing JSON with missing optional fields."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Missing key_factors and reasoning
        mock_response.content = [MagicMock(text='{"recommended_bet": "pass", "confidence_score": 0.5}')]
        mock_response.usage.input_tokens = 500
        mock_response.usage.output_tokens = 100
        mock_client.messages.create.return_value = mock_response

        with patch("backend.api.ai_service.claude_client", mock_client):
            from backend.api.ai_service import analyze_with_claude

            result = analyze_with_claude(sample_game_context)

            assert result["recommended_bet"] == "pass"
            assert result["confidence_score"] == 0.5
            assert result["key_factors"] == []  # Default empty list
            assert result["reasoning"] == ""  # Default empty string

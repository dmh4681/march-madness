"""
Test Utilities and Fixture Data for Betting Market Data (Task #12)

Comprehensive test suite covering:
- Mock spread data factories for various game scenarios
- Mock game result data with final scores
- Expected edge calculation tests (american_odds_to_prob, calculate_ev, get_kelly_stake)
- ATS (Against The Spread) result calculations
- Wilson confidence interval validation
- Validate edge statistical testing
- Arbitrage detection with mock prediction market data
- Odds monitor movement detection
- Baseline model prediction utilities
"""

import pytest
import math
import numpy as np
import pandas as pd
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime


# ============================================================================
# BETTING MARKET DATA FACTORIES
# ============================================================================

class SpreadFactory:
    """Factory for generating realistic spread data for tests."""

    @staticmethod
    def heavy_favorite(home_spread=-12.5, home_ml=-550, away_ml=400):
        """Heavy favorite scenario (e.g., #1 Duke vs unranked team)."""
        return {
            "home_spread": home_spread,
            "away_spread": -home_spread,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": 148.5,
        }

    @staticmethod
    def moderate_favorite(home_spread=-7.5, home_ml=-280, away_ml=220):
        """Moderate favorite (e.g., ranked team in conference game)."""
        return {
            "home_spread": home_spread,
            "away_spread": -home_spread,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": 145.5,
        }

    @staticmethod
    def slight_favorite(home_spread=-3.0, home_ml=-155, away_ml=130):
        """Slight favorite (e.g., evenly matched conference rivals)."""
        return {
            "home_spread": home_spread,
            "away_spread": -home_spread,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": 140.0,
        }

    @staticmethod
    def pick_em(home_ml=-110, away_ml=-110):
        """Pick'em game (no spread, even odds)."""
        return {
            "home_spread": 0.0,
            "away_spread": 0.0,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": 142.0,
        }

    @staticmethod
    def home_underdog(home_spread=4.5, home_ml=160, away_ml=-190):
        """Home team is the underdog."""
        return {
            "home_spread": home_spread,
            "away_spread": -home_spread,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": 138.5,
        }

    @staticmethod
    def custom(home_spread, home_ml, away_ml, over_under=145.0):
        """Custom spread scenario."""
        return {
            "home_spread": home_spread,
            "away_spread": -home_spread,
            "home_ml": home_ml,
            "away_ml": away_ml,
            "over_under": over_under,
        }


class GameResultFactory:
    """Factory for generating game results with final scores."""

    @staticmethod
    def home_blowout(home_score=88, away_score=65):
        """Home team wins by 20+."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }

    @staticmethod
    def home_comfortable_win(home_score=78, away_score=68):
        """Home team wins by ~10."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }

    @staticmethod
    def home_close_win(home_score=72, away_score=69):
        """Home team wins by 1-3."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }

    @staticmethod
    def away_upset(home_score=65, away_score=71):
        """Away team wins (upset)."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }

    @staticmethod
    def overtime_game(home_score=85, away_score=82):
        """High-scoring overtime game."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
            "overtime": True,
        }

    @staticmethod
    def low_scoring(home_score=55, away_score=48):
        """Low-scoring defensive battle."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }

    @staticmethod
    def custom(home_score, away_score):
        """Custom result."""
        return {
            "home_score": home_score,
            "away_score": away_score,
            "margin": home_score - away_score,
            "total_points": home_score + away_score,
        }


class PredictionMarketFactory:
    """Factory for generating prediction market data."""

    @staticmethod
    def polymarket_home_heavy(game_id, home_team="Duke", away_team="UNC"):
        """Polymarket favoring home team heavily (70/30)."""
        return {
            "id": f"pm-{game_id}-poly",
            "game_id": game_id,
            "platform": "polymarket",
            "question": f"Will {home_team} beat {away_team}?",
            "outcomes": [
                {"name": home_team, "price": 0.70},
                {"name": away_team, "price": 0.30},
            ],
        }

    @staticmethod
    def polymarket_close(game_id, home_team="Duke", away_team="UNC"):
        """Polymarket showing close game (55/45)."""
        return {
            "id": f"pm-{game_id}-poly",
            "game_id": game_id,
            "platform": "polymarket",
            "question": f"Will {home_team} beat {away_team}?",
            "outcomes": [
                {"name": home_team, "price": 0.55},
                {"name": away_team, "price": 0.45},
            ],
        }

    @staticmethod
    def kalshi_with_edge(game_id, home_team="Duke", away_team="UNC",
                         home_price=0.75, away_price=0.25):
        """Kalshi market showing potential edge vs sportsbook."""
        return {
            "id": f"pm-{game_id}-kalshi",
            "game_id": game_id,
            "platform": "kalshi",
            "question": f"Will {home_team} beat {away_team}?",
            "outcomes": [
                {"name": home_team, "price": home_price},
                {"name": away_team, "price": away_price},
            ],
        }

    @staticmethod
    def yes_no_format(game_id, yes_price=0.65, no_price=0.35):
        """Market using Yes/No format instead of team names."""
        return {
            "id": f"pm-{game_id}-yn",
            "game_id": game_id,
            "platform": "polymarket",
            "question": "Will the home team win?",
            "outcomes": [
                {"name": "Yes", "price": yes_price},
                {"name": "No", "price": no_price},
            ],
        }


class EdgeCalculationFactory:
    """Factory for expected edge calculation test cases."""

    @staticmethod
    def clear_edge():
        """Game where analytics clearly favor one side."""
        return {
            "home_spread": -7.5,
            "home_ml": -280,
            "away_ml": 220,
            "model_prob_home_cover": 0.62,
            "expected_edge_pct": 12.0,  # |0.62 - 0.50| * 100
            "expected_confidence": "high",
            "expected_recommendation": "home_spread",
        }

    @staticmethod
    def marginal_edge():
        """Game with slight edge."""
        return {
            "home_spread": -3.0,
            "home_ml": -155,
            "away_ml": 130,
            "model_prob_home_cover": 0.56,
            "expected_edge_pct": 6.0,
            "expected_confidence": "medium",
            "expected_recommendation": "home_spread",
        }

    @staticmethod
    def no_edge():
        """Game with no actionable edge."""
        return {
            "home_spread": -5.0,
            "home_ml": -200,
            "away_ml": 170,
            "model_prob_home_cover": 0.52,
            "expected_edge_pct": 2.0,
            "expected_confidence": "low",
            "expected_recommendation": "pass",
        }

    @staticmethod
    def contrarian_edge():
        """Game where value is on the underdog (contrarian bet)."""
        return {
            "home_spread": -10.0,
            "home_ml": -400,
            "away_ml": 300,
            "model_prob_away_cover": 0.58,
            "expected_edge_pct": 8.0,
            "expected_confidence": "medium",
            "expected_recommendation": "away_spread",
        }


# ============================================================================
# TESTS: AMERICAN ODDS TO PROBABILITY CONVERSION
# ============================================================================

class TestAmericanOddsConversion:
    """Tests for american_odds_to_prob() in arbitrage_detector.py."""

    def test_standard_minus_110(self):
        """Standard vig line: -110 -> ~52.38%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(-110)
        assert abs(prob - 0.5238) < 0.001

    def test_heavy_favorite_minus_300(self):
        """-300 favorite -> 75%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(-300)
        assert abs(prob - 0.75) < 0.001

    def test_heavy_favorite_minus_500(self):
        """-500 favorite -> ~83.3%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(-500)
        expected = 500 / (500 + 100)
        assert abs(prob - expected) < 0.001

    def test_slight_favorite_minus_150(self):
        """-150 -> 60%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(-150)
        assert abs(prob - 0.60) < 0.001

    def test_slight_underdog_plus_130(self):
        """+130 -> ~43.5%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(130)
        expected = 100 / (130 + 100)
        assert abs(prob - expected) < 0.001

    def test_moderate_underdog_plus_200(self):
        """+200 -> ~33.3%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(200)
        expected = 100 / (200 + 100)
        assert abs(prob - expected) < 0.001

    def test_heavy_underdog_plus_500(self):
        """+500 -> ~16.7%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(500)
        expected = 100 / (500 + 100)
        assert abs(prob - expected) < 0.001

    def test_even_money_plus_100(self):
        """+100 (even money) -> 50%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(100)
        assert abs(prob - 0.50) < 0.001

    def test_none_odds_default(self):
        """None odds should default to 50%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(None)
        assert prob == 0.5

    def test_extreme_favorite_minus_10000(self):
        """-10000 -> ~99%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(-10000)
        expected = 10000 / (10000 + 100)
        assert abs(prob - expected) < 0.001

    def test_extreme_underdog_plus_10000(self):
        """+10000 -> ~1%."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        prob = american_odds_to_prob(10000)
        expected = 100 / (10000 + 100)
        assert abs(prob - expected) < 0.001

    def test_probabilities_sum_with_vig(self):
        """Home + away implied probs should sum to > 1 (vig)."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        # Standard -110/-110 line
        home_prob = american_odds_to_prob(-110)
        away_prob = american_odds_to_prob(-110)
        total = home_prob + away_prob
        # With vig, total should exceed 1.0
        assert total > 1.0
        # Vig is ~4.76% for -110/-110
        assert abs(total - 1.0476) < 0.01

    def test_probabilities_favorite_underdog_pair(self):
        """-280/+220 pair: probs sum > 1 due to vig."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob
        home_prob = american_odds_to_prob(-280)
        away_prob = american_odds_to_prob(220)
        total = home_prob + away_prob
        assert total > 1.0
        # Home should be much higher
        assert home_prob > away_prob


# ============================================================================
# TESTS: EXPECTED VALUE CALCULATION
# ============================================================================

class TestExpectedValue:
    """Tests for calculate_ev() in arbitrage_detector.py."""

    def test_positive_ev_favorite(self):
        """Positive EV when your estimated prob exceeds implied prob."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        # Your prob: 60%, sportsbook: 52.4%, odds: -110
        ev = calculate_ev(your_prob=0.60, sportsbook_prob=0.524, odds=-110)
        assert ev > 0  # Should be positive EV

    def test_negative_ev_bad_bet(self):
        """Negative EV when your estimated prob is below implied prob."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        # Your prob: 40%, sportsbook: 52.4%, odds: -110
        ev = calculate_ev(your_prob=0.40, sportsbook_prob=0.524, odds=-110)
        assert ev < 0  # Should be negative EV

    def test_zero_ev_at_breakeven(self):
        """EV near zero when prob matches breakeven."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        # At -110 odds, breakeven is 52.38%
        ev = calculate_ev(your_prob=0.5238, sportsbook_prob=0.5238, odds=-110)
        assert abs(ev) < 1.0  # Should be very close to zero

    def test_ev_underdog_bet(self):
        """Positive EV on underdog when market overprices favorite."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        # Your prob: 45% for underdog, odds +200
        ev = calculate_ev(your_prob=0.45, sportsbook_prob=0.333, odds=200)
        assert ev > 0  # Positive EV since 45% > 33.3% implied

    def test_ev_heavy_favorite(self):
        """EV calculation for heavy favorite bet."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        # Your prob: 80%, odds -300
        ev = calculate_ev(your_prob=0.80, sportsbook_prob=0.75, odds=-300)
        assert ev > 0  # Positive because 80% > 75% implied

    def test_ev_symmetry(self):
        """EV should be symmetric -- higher prob = higher EV."""
        from backend.data_collection.arbitrage_detector import calculate_ev
        ev_low = calculate_ev(your_prob=0.55, sportsbook_prob=0.50, odds=-110)
        ev_high = calculate_ev(your_prob=0.65, sportsbook_prob=0.50, odds=-110)
        assert ev_high > ev_low


# ============================================================================
# TESTS: KELLY CRITERION STAKE SIZING
# ============================================================================

class TestKellyCriterion:
    """Tests for get_kelly_stake() in arbitrage_detector.py."""

    def test_kelly_positive_edge(self):
        """Kelly recommends a bet when edge exists."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # 60% win prob at -110 odds, quarter Kelly
        stake = get_kelly_stake(your_prob=0.60, odds=-110, fraction=0.25)
        assert stake > 0
        # Quarter Kelly should be modest
        assert stake < 0.10

    def test_kelly_no_edge(self):
        """Kelly recommends zero stake when no edge."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # 45% win prob at -110 -- negative edge
        stake = get_kelly_stake(your_prob=0.45, odds=-110)
        assert stake == 0

    def test_kelly_at_breakeven(self):
        """Kelly near zero at breakeven probability."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # At -110, breakeven ~ 52.4%
        stake = get_kelly_stake(your_prob=0.524, odds=-110)
        # Should be zero or very small
        assert stake < 0.005

    def test_kelly_full_vs_quarter(self):
        """Full Kelly is 4x quarter Kelly."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        full = get_kelly_stake(your_prob=0.60, odds=-110, fraction=1.0)
        quarter = get_kelly_stake(your_prob=0.60, odds=-110, fraction=0.25)
        assert abs(full - quarter * 4) < 0.001

    def test_kelly_underdog_odds(self):
        """Kelly works with underdog (positive) odds."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # 40% prob at +200 odds -- has edge (implied 33.3%)
        stake = get_kelly_stake(your_prob=0.40, odds=200, fraction=1.0)
        assert stake > 0

    def test_kelly_heavy_favorite(self):
        """Kelly stake for heavy favorite."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # 80% prob at -300 odds
        stake = get_kelly_stake(your_prob=0.80, odds=-300, fraction=0.25)
        assert stake > 0

    def test_kelly_never_exceeds_fraction(self):
        """Kelly stake should never exceed the fraction parameter."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        # Even with very high edge
        stake = get_kelly_stake(your_prob=0.95, odds=100, fraction=0.25)
        assert stake <= 0.25

    def test_kelly_default_quarter(self):
        """Default fraction is 0.25 (quarter Kelly)."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake
        default = get_kelly_stake(your_prob=0.60, odds=-110)
        quarter = get_kelly_stake(your_prob=0.60, odds=-110, fraction=0.25)
        assert default == quarter


# ============================================================================
# TESTS: ARBITRAGE DETECTION
# ============================================================================

class TestArbitrageDetection:
    """Tests for detect_arbitrage() and scan_game_for_arbitrage()."""

    def test_detect_home_ml_arbitrage_actionable(self):
        """Detect actionable arbitrage on home ML when PM differs by >= 10%."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-1",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -150,  # Implied ~60%
            "away_ml": 130,
        }
        # PM: Duke 72% vs sportsbook 60% -> delta ~12%
        market = {
            "id": "pm-game-1",
            "game_id": "game-1",
            "outcomes": [
                {"name": "Duke", "price": 0.72},
                {"name": "UNC", "price": 0.28},
            ],
        }

        result = detect_arbitrage(game, market, "home_ml")
        assert result is not None
        assert result["is_actionable"] == True
        assert result["delta"] >= 10.0
        assert result["edge_direction"] == "prediction_higher"

    def test_detect_home_ml_no_arbitrage(self):
        """No actionable arbitrage when PM and sportsbook align."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-2",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -150,  # Implied ~60%
        }
        # PM price close to sportsbook implied
        market = {
            "id": "pm-2",
            "game_id": "game-2",
            "outcomes": [
                {"name": "Duke", "price": 0.62},
                {"name": "UNC", "price": 0.38},
            ],
        }

        result = detect_arbitrage(game, market, "home_ml")
        assert result is not None
        assert result["is_actionable"] is False
        assert result["delta"] < 10.0

    def test_detect_away_ml_arbitrage(self):
        """Detect arbitrage on away ML."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-3",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -280,
            "away_ml": 220,  # Implied ~31.25%
        }
        market = {
            "id": "pm-3",
            "game_id": "game-3",
            "outcomes": [
                {"name": "Duke", "price": 0.55},
                {"name": "UNC", "price": 0.45},  # 45% vs 31.25% = big delta
            ],
        }

        result = detect_arbitrage(game, market, "away_ml")
        assert result is not None
        assert result["is_actionable"] is True
        assert result["edge_direction"] == "prediction_higher"

    def test_detect_spread_arbitrage(self):
        """Spread bets use fixed 52.38% implied probability."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-4",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -280,
        }
        market = {
            "id": "pm-4",
            "game_id": "game-4",
            "outcomes": [
                {"name": "Duke", "price": 0.70},  # 70% vs 52.38% = ~17.6% delta
            ],
        }

        result = detect_arbitrage(game, market, "home_spread")
        assert result is not None
        assert result["is_actionable"] is True
        assert abs(result["sportsbook_implied_prob"] - 0.5238) < 0.001

    def test_detect_unknown_bet_type(self):
        """Unknown bet type returns None."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {"id": "game-5", "home_team": "Duke", "away_team": "UNC"}
        market = {"outcomes": []}

        result = detect_arbitrage(game, market, "over_under")
        assert result is None

    def test_detect_no_matching_outcome(self):
        """No matching outcome in market returns None."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-6",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -150,
        }
        market = {
            "id": "pm-6",
            "game_id": "game-6",
            "outcomes": [
                {"name": "Kentucky", "price": 0.60},  # Wrong team
            ],
        }

        result = detect_arbitrage(game, market, "home_ml")
        assert result is None

    def test_detect_yes_no_format(self):
        """Markets with Yes/No format match home/away correctly."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-7",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -150,  # Implied ~60%
        }
        market = PredictionMarketFactory.yes_no_format("game-7", yes_price=0.75)

        result = detect_arbitrage(game, market, "home_ml")
        assert result is not None
        assert result["prediction_market_prob"] == 0.75
        assert result["is_actionable"] is True

    def test_sportsbook_higher_direction(self):
        """Edge direction is sportsbook_higher when PM < sportsbook."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage

        game = {
            "id": "game-8",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -300,  # Implied 75%
        }
        market = {
            "id": "pm-8",
            "game_id": "game-8",
            "outcomes": [
                {"name": "Duke", "price": 0.55},  # PM 55% < SB 75%
            ],
        }

        result = detect_arbitrage(game, market, "home_ml")
        assert result is not None
        assert result["edge_direction"] == "sportsbook_higher"
        assert result["is_actionable"] is True

    @pytest.mark.asyncio
    async def test_scan_game_multiple_markets(self):
        """Scan a game against multiple prediction markets."""
        from backend.data_collection.arbitrage_detector import scan_game_for_arbitrage

        game = {
            "id": "game-scan-1",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": -150,  # Implied ~60%
            "away_ml": 130,   # Implied ~43.5%
        }
        markets = [
            PredictionMarketFactory.polymarket_home_heavy("game-scan-1", "Duke", "UNC"),
            PredictionMarketFactory.kalshi_with_edge("game-scan-1", "Duke", "UNC",
                                                     home_price=0.75, away_price=0.25),
        ]

        opportunities = await scan_game_for_arbitrage(game, markets)
        # Should find opportunities from both markets (home_ml and away_ml for each)
        assert len(opportunities) > 0
        # All should reference the correct game
        for opp in opportunities:
            assert opp["game_id"] == "game-scan-1"

    @pytest.mark.asyncio
    async def test_scan_game_filters_wrong_game(self):
        """Markets for other games are skipped."""
        from backend.data_collection.arbitrage_detector import scan_game_for_arbitrage

        game = {"id": "game-scan-2", "home_team": "Duke", "away_team": "UNC",
                "home_ml": -150, "away_ml": 130}
        markets = [
            PredictionMarketFactory.polymarket_home_heavy("different-game", "Kentucky", "Kansas"),
        ]

        opportunities = await scan_game_for_arbitrage(game, markets)
        assert len(opportunities) == 0


# ============================================================================
# TESTS: ODDS MONITOR MOVEMENT DETECTION
# ============================================================================

class TestOddsMonitorMovement:
    """Tests for OddsMovement and OddsMonitor in odds_monitor.py."""

    def test_ml_to_implied_prob_favorite(self):
        """Moneyline to implied probability for favorite."""
        from backend.services.odds_monitor import _ml_to_implied_prob
        prob = _ml_to_implied_prob(-150)
        assert abs(prob - 0.60) < 0.001

    def test_ml_to_implied_prob_underdog(self):
        """Moneyline to implied probability for underdog."""
        from backend.services.odds_monitor import _ml_to_implied_prob
        prob = _ml_to_implied_prob(200)
        expected = 100 / (200 + 100)
        assert abs(prob - expected) < 0.001

    def test_ml_to_implied_prob_zero(self):
        """Zero moneyline returns 50%."""
        from backend.services.odds_monitor import _ml_to_implied_prob
        prob = _ml_to_implied_prob(0)
        assert prob == 0.5

    def test_odds_movement_spread_change(self):
        """Spread movement is current - previous."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g1", home_team="Duke", away_team="UNC",
            previous_spread=-7.5, current_spread=-5.5,
            previous_home_ml=-280, current_home_ml=-200,
            previous_away_ml=220, current_away_ml=170,
        )
        assert movement.spread_movement == 2.0  # -5.5 - (-7.5) = 2.0

    def test_odds_movement_significant_spread(self):
        """Movement >= 2.0 points is significant."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g2", home_team="Duke", away_team="UNC",
            previous_spread=-7.5, current_spread=-5.0,
            previous_home_ml=None, current_home_ml=None,
            previous_away_ml=None, current_away_ml=None,
        )
        assert movement.spread_movement == 2.5
        assert movement.is_significant is True

    def test_odds_movement_not_significant(self):
        """Small spread movement is not significant."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g3", home_team="Duke", away_team="UNC",
            previous_spread=-7.5, current_spread=-7.0,
            previous_home_ml=-280, current_home_ml=-270,
            previous_away_ml=220, current_away_ml=210,
        )
        assert movement.is_significant is False

    def test_odds_movement_significant_prob_change(self):
        """Large implied probability movement is significant (>= 10%)."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g4", home_team="Duke", away_team="UNC",
            previous_spread=None, current_spread=None,
            previous_home_ml=-150, current_home_ml=-300,  # 60% -> 75% = 15% change
            previous_away_ml=130, current_away_ml=250,
        )
        assert movement.home_prob_movement is not None
        assert abs(movement.home_prob_movement) >= 0.10
        assert movement.is_significant is True

    def test_odds_movement_none_spread(self):
        """Movement with None spread returns None for spread_movement."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g5", home_team="Duke", away_team="UNC",
            previous_spread=None, current_spread=-7.5,
            previous_home_ml=None, current_home_ml=None,
            previous_away_ml=None, current_away_ml=None,
        )
        assert movement.spread_movement is None

    def test_odds_movement_to_dict(self):
        """to_dict() returns all expected fields."""
        from backend.services.odds_monitor import OddsMovement
        movement = OddsMovement(
            game_id="g6", home_team="Duke", away_team="UNC",
            previous_spread=-7.5, current_spread=-5.5,
            previous_home_ml=-280, current_home_ml=-200,
            previous_away_ml=220, current_away_ml=170,
        )
        d = movement.to_dict()
        assert d["game_id"] == "g6"
        assert d["home_team"] == "Duke"
        assert d["spread_movement"] == 2.0
        assert "is_significant" in d
        assert "detected_at" in d
        assert "home_prob_movement" in d

    def test_odds_monitor_no_api_key(self):
        """Monitor returns empty list when no API key configured."""
        from backend.services.odds_monitor import OddsMonitor
        with patch.dict("os.environ", {}, clear=True):
            with patch("backend.services.odds_monitor.ODDS_API_KEY", None):
                monitor = OddsMonitor()
                result = monitor.fetch_current_odds()
                assert result == []

    def test_odds_monitor_get_game_no_movements(self):
        """get_game_movement returns None when no movements stored."""
        from backend.services.odds_monitor import OddsMonitor
        monitor = OddsMonitor()
        assert monitor.get_game_movement("nonexistent-game") is None


# ============================================================================
# TESTS: ATS (AGAINST THE SPREAD) CALCULATIONS
# ============================================================================

class TestATSCalculations:
    """Tests for calculate_ats_result() and identify_underdog() in validate_edge.py."""

    def _make_game_row(self, home_team, away_team, home_rank, away_rank,
                       home_score, away_score):
        """Helper to create a pandas Series resembling a game row."""
        return pd.Series({
            "home_team": home_team,
            "away_team": away_team,
            "home_ap_rank": home_rank,
            "away_ap_rank": away_rank,
            "home_score": home_score,
            "away_score": away_score,
        })

    def test_identify_underdog_home_ranked(self):
        """When home team is ranked and away is not, away is underdog."""
        from backend.analysis.validate_edge import identify_underdog
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 80, 70)
        result = identify_underdog(row)
        assert result is not None
        assert result["underdog"] == "away"
        assert result["underdog_team"] == "Wake Forest"
        assert result["favorite_team"] == "Duke"
        assert result["favorite_rank"] == 5

    def test_identify_underdog_away_ranked(self):
        """When away team is ranked and home is not, home is underdog."""
        from backend.analysis.validate_edge import identify_underdog
        row = self._make_game_row("Wake Forest", "Duke", float("nan"), 5, 70, 80)
        result = identify_underdog(row)
        assert result is not None
        assert result["underdog"] == "home"
        assert result["underdog_team"] == "Wake Forest"

    def test_identify_underdog_both_ranked(self):
        """Both teams ranked -> None (doesn't match target scenario)."""
        from backend.analysis.validate_edge import identify_underdog
        row = self._make_game_row("Duke", "UNC", 5, 8, 80, 75)
        result = identify_underdog(row)
        assert result is None

    def test_identify_underdog_neither_ranked(self):
        """Neither team ranked -> None."""
        from backend.analysis.validate_edge import identify_underdog
        row = self._make_game_row("Wake Forest", "Boston College",
                                  float("nan"), float("nan"), 70, 65)
        result = identify_underdog(row)
        assert result is None

    def test_ats_underdog_wins_outright_no_spread(self):
        """Underdog wins outright without spread data -> 'win'."""
        from backend.analysis.validate_edge import calculate_ats_result
        # Away underdog (unranked) beats home ranked team
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 65, 70)
        result = calculate_ats_result(row)
        assert result == "win"

    def test_ats_underdog_loses_no_spread(self):
        """Underdog loses without spread data -> 'loss'."""
        from backend.analysis.validate_edge import calculate_ats_result
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 80, 65)
        result = calculate_ats_result(row)
        assert result == "loss"

    def test_ats_underdog_covers_with_spread(self):
        """Underdog covers the spread (loses by less than spread)."""
        from backend.analysis.validate_edge import calculate_ats_result
        # Duke #5 at home, Wake Forest unranked away
        # Duke wins 75-70 (margin = -5 from underdog perspective)
        # Spread = 7 (favorite -7, underdog +7)
        # Underdog lost by 5, spread was 7 -> underdog covers
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 75, 70)
        result = calculate_ats_result(row, spread=7)
        assert result == "cover"

    def test_ats_underdog_fails_to_cover(self):
        """Underdog fails to cover (loses by more than spread)."""
        from backend.analysis.validate_edge import calculate_ats_result
        # Duke wins 85-65 (margin = -20 from underdog perspective)
        # Spread = 7 -> underdog doesn't cover
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 85, 65)
        result = calculate_ats_result(row, spread=7)
        assert result == "loss"

    def test_ats_push_exact_spread(self):
        """Exact spread results in a push."""
        from backend.analysis.validate_edge import calculate_ats_result
        # Duke wins 75-68 (margin = -7 from underdog perspective)
        # Spread = 7 -> exact push
        row = self._make_game_row("Duke", "Wake Forest", 5, float("nan"), 75, 68)
        result = calculate_ats_result(row, spread=7)
        assert result == "push"

    def test_ats_both_ranked_returns_none(self):
        """Both teams ranked returns None (no underdog identified)."""
        from backend.analysis.validate_edge import calculate_ats_result
        row = self._make_game_row("Duke", "UNC", 5, 8, 80, 75)
        result = calculate_ats_result(row)
        assert result is None


# ============================================================================
# TESTS: WILSON CONFIDENCE INTERVAL
# ============================================================================

class TestWilsonConfidenceInterval:
    """Tests for wilson_confidence_interval() in validate_edge.py."""

    def test_wilson_50_percent(self):
        """50% rate with reasonable sample should produce interval around 0.5."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        low, high = wilson_confidence_interval(50, 100, confidence=0.95)
        assert low < 0.50
        assert high > 0.50
        # Interval should be reasonable width
        assert high - low < 0.20

    def test_wilson_100_percent(self):
        """100% success rate should produce high interval near 1.0."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        low, high = wilson_confidence_interval(100, 100, confidence=0.95)
        assert high <= 1.0
        assert low > 0.90

    def test_wilson_0_percent(self):
        """0% success rate should produce low interval near 0.0."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        low, high = wilson_confidence_interval(0, 100, confidence=0.95)
        assert low >= 0.0
        assert high < 0.10

    def test_wilson_zero_trials(self):
        """Zero trials returns (0, 0)."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        low, high = wilson_confidence_interval(0, 0, confidence=0.95)
        assert low == 0
        assert high == 0

    def test_wilson_small_sample(self):
        """Small sample produces wider interval."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        small_low, small_high = wilson_confidence_interval(5, 10, confidence=0.95)
        large_low, large_high = wilson_confidence_interval(500, 1000, confidence=0.95)
        small_width = small_high - small_low
        large_width = large_high - large_low
        assert small_width > large_width

    def test_wilson_interval_contains_proportion(self):
        """The observed proportion should be within the interval."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        successes, trials = 55, 100
        low, high = wilson_confidence_interval(successes, trials, confidence=0.95)
        proportion = successes / trials
        assert low <= proportion <= high

    def test_wilson_higher_confidence_wider(self):
        """99% CI should be wider than 95% CI."""
        from backend.analysis.validate_edge import wilson_confidence_interval
        low_95, high_95 = wilson_confidence_interval(55, 100, confidence=0.95)
        low_99, high_99 = wilson_confidence_interval(55, 100, confidence=0.99)
        width_95 = high_95 - low_95
        width_99 = high_99 - low_99
        assert width_99 > width_95


# ============================================================================
# TESTS: VALIDATE EDGE STATISTICAL ANALYSIS
# ============================================================================

class TestValidateEdge:
    """Tests for validate_edge() in validate_edge.py."""

    def _make_games_df(self, n_wins, n_losses, use_spread=False):
        """Helper to create a DataFrame of games with known outcomes."""
        games = []
        for i in range(n_wins):
            game = {
                "game_id": f"game-{i}",
                "date": "2025-01-15",
                "home_team": "Duke",
                "away_team": f"Team{i}",
                "home_ap_rank": 5,
                "away_ap_rank": float("nan"),
                "home_score": 70,
                "away_score": 75,  # Underdog (away) wins
                "same_conference": True,
                "ranked_vs_unranked": True,
            }
            if use_spread:
                game["spread"] = 7.0
            games.append(game)

        for i in range(n_losses):
            game = {
                "game_id": f"game-loss-{i}",
                "date": "2025-01-15",
                "home_team": "Duke",
                "away_team": f"LossTeam{i}",
                "home_ap_rank": 5,
                "away_ap_rank": float("nan"),
                "home_score": 85,
                "away_score": 65,  # Underdog (away) loses
                "same_conference": True,
                "ranked_vs_unranked": True,
            }
            if use_spread:
                game["spread"] = 7.0
            games.append(game)

        return pd.DataFrame(games)

    def test_validate_edge_exists(self):
        """Edge validated when win% > 52.4% AND p < 0.05."""
        from backend.analysis.validate_edge import validate_edge
        # 60% win rate with large sample
        df = self._make_games_df(n_wins=120, n_losses=80)
        result = validate_edge(df, use_spread=False)

        assert "error" not in result
        assert result["sample_size"] == 200
        assert result["wins"] == 120
        assert result["losses"] == 80
        assert result["win_percentage"] == 0.60
        assert result["win_percentage"] > result["breakeven_threshold"]
        # With 60% over 200 games, should be significant
        assert result["p_value"] < 0.05
        assert result["edge_exists"] == True

    def test_validate_no_edge_low_winrate(self):
        """No edge when win% <= breakeven."""
        from backend.analysis.validate_edge import validate_edge
        # 48% win rate
        df = self._make_games_df(n_wins=48, n_losses=52)
        result = validate_edge(df, use_spread=False)

        assert result["win_percentage"] < result["breakeven_threshold"]
        assert result["edge_exists"] == False

    def test_validate_edge_possible_small_sample(self):
        """Edge possible but not significant with small sample."""
        from backend.analysis.validate_edge import validate_edge
        # 60% win rate but only 20 games -- not statistically significant
        df = self._make_games_df(n_wins=12, n_losses=8)
        result = validate_edge(df, use_spread=False)

        assert result["win_percentage"] == 0.60
        # With only 20 games, p-value likely >= 0.05
        # (May or may not be significant depending on test specifics)
        assert result["sample_size"] == 20

    def test_validate_empty_games(self):
        """No valid games returns error."""
        from backend.analysis.validate_edge import validate_edge
        # Both teams ranked -> no valid underdog
        df = pd.DataFrame([{
            "game_id": "g1",
            "date": "2025-01-15",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ap_rank": 5,
            "away_ap_rank": 8,
            "home_score": 80,
            "away_score": 75,
            "same_conference": True,
            "ranked_vs_unranked": True,
        }])
        result = validate_edge(df, use_spread=False)
        assert "error" in result

    def test_validate_with_pushes(self):
        """Pushes are tracked but excluded from win percentage."""
        from backend.analysis.validate_edge import validate_edge
        games = []
        # 10 wins
        for i in range(10):
            games.append({
                "game_id": f"w-{i}", "date": "2025-01-15",
                "home_team": "Duke", "away_team": f"T{i}",
                "home_ap_rank": 5, "away_ap_rank": float("nan"),
                "home_score": 70, "away_score": 70,  # Tie = push
                "same_conference": True, "ranked_vs_unranked": True,
            })
        # Also add some clear wins and losses
        for i in range(30):
            games.append({
                "game_id": f"win-{i}", "date": "2025-01-15",
                "home_team": "Duke", "away_team": f"W{i}",
                "home_ap_rank": 5, "away_ap_rank": float("nan"),
                "home_score": 70, "away_score": 75,  # Underdog wins
                "same_conference": True, "ranked_vs_unranked": True,
            })
        for i in range(20):
            games.append({
                "game_id": f"loss-{i}", "date": "2025-01-15",
                "home_team": "Duke", "away_team": f"L{i}",
                "home_ap_rank": 5, "away_ap_rank": float("nan"),
                "home_score": 85, "away_score": 65,
                "same_conference": True, "ranked_vs_unranked": True,
            })
        df = pd.DataFrame(games)
        result = validate_edge(df, use_spread=False)

        assert result["pushes"] == 10
        # Win % calculated without pushes
        assert result["sample_size"] == 50  # 30 wins + 20 losses
        assert result["win_percentage"] == 0.60

    def test_validate_analysis_type_straight_up(self):
        """Without spread, analysis_type is 'Straight-Up (proxy)'."""
        from backend.analysis.validate_edge import validate_edge
        df = self._make_games_df(n_wins=30, n_losses=20)
        result = validate_edge(df, use_spread=False)
        assert result["analysis_type"] == "Straight-Up (proxy)"

    def test_validate_analysis_type_ats(self):
        """With spread, analysis_type is 'ATS'."""
        from backend.analysis.validate_edge import validate_edge
        df = self._make_games_df(n_wins=30, n_losses=20, use_spread=True)
        result = validate_edge(df, use_spread=True)
        assert result["analysis_type"] == "ATS"

    def test_validate_results_df_included(self):
        """Results include a detailed results_df DataFrame."""
        from backend.analysis.validate_edge import validate_edge
        df = self._make_games_df(n_wins=20, n_losses=10)
        result = validate_edge(df, use_spread=False)
        assert "results_df" in result
        assert isinstance(result["results_df"], pd.DataFrame)
        assert len(result["results_df"]) == 30

    def test_validate_ci_bounds(self):
        """Confidence interval bounds are valid (between 0 and 1)."""
        from backend.analysis.validate_edge import validate_edge
        df = self._make_games_df(n_wins=55, n_losses=45)
        result = validate_edge(df, use_spread=False)
        assert 0 <= result["ci_95_low"] <= 1
        assert 0 <= result["ci_95_high"] <= 1
        assert result["ci_95_low"] < result["ci_95_high"]


# ============================================================================
# TESTS: BASELINE MODEL PREDICTION UTILITIES
# ============================================================================

class TestBaselineModelUtilities:
    """Tests for predict_game() and related functions in baseline.py."""

    def _create_mock_model(self, proba_value):
        """Create a mock LogisticRegression model with fixed probability."""
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = np.array([[1 - proba_value, proba_value]])
        return mock_model

    def test_predict_high_confidence(self):
        """P >= 0.60 -> BET_UNDERDOG, HIGH confidence."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.65)
        result = predict_game(model, {"favorite_rank": 10, "is_home": 1, "season_progress": 0.5})
        assert result["recommendation"] == "BET_UNDERDOG"
        assert result["confidence"] == "HIGH"
        assert result["cover_probability"] == 0.65

    def test_predict_medium_confidence(self):
        """0.55 <= P < 0.60 -> LEAN_UNDERDOG, MEDIUM confidence."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.57)
        result = predict_game(model, {"favorite_rank": 15, "is_home": 0, "season_progress": 0.3})
        assert result["recommendation"] == "LEAN_UNDERDOG"
        assert result["confidence"] == "MEDIUM"

    def test_predict_low_confidence(self):
        """P < 0.55 -> PASS, LOW confidence."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.51)
        result = predict_game(model, {"favorite_rank": 20, "is_home": 0, "season_progress": 0.8})
        assert result["recommendation"] == "PASS"
        assert result["confidence"] == "LOW"

    def test_predict_edge_vs_breakeven(self):
        """Edge is calculated as prob - 0.524."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.60)
        result = predict_game(model, {"favorite_rank": 10})
        expected_edge = 0.60 - 0.524
        assert abs(result["edge_vs_breakeven"] - expected_edge) < 0.001

    def test_predict_negative_edge(self):
        """Negative edge when prob < breakeven."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.48)
        result = predict_game(model, {"favorite_rank": 3, "is_home": 0})
        assert result["edge_vs_breakeven"] < 0

    def test_predict_rank_tier_calculation(self):
        """Verify rank tier assignment: 1-5=1, 6-15=2, 16-25=3."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.55)

        # Top 5 -> tier 1
        result = predict_game(model, {"favorite_rank": 3})
        # Verify the model received correct features (rank_tier=1)
        call_args = model.predict_proba.call_args[0][0]
        assert call_args["rank_tier"].values[0] == 1

        # Rank 10 -> tier 2
        predict_game(model, {"favorite_rank": 10})
        call_args = model.predict_proba.call_args[0][0]
        assert call_args["rank_tier"].values[0] == 2

        # Rank 20 -> tier 3
        predict_game(model, {"favorite_rank": 20})
        call_args = model.predict_proba.call_args[0][0]
        assert call_args["rank_tier"].values[0] == 3

    def test_predict_rank_inverse(self):
        """rank_inverse = 26 - favorite_rank."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.55)
        predict_game(model, {"favorite_rank": 10})
        call_args = model.predict_proba.call_args[0][0]
        assert call_args["rank_inverse"].values[0] == 16  # 26 - 10

    def test_predict_default_season_progress(self):
        """Season progress defaults to 0.5 if not provided."""
        from backend.models.baseline import predict_game
        model = self._create_mock_model(0.55)
        predict_game(model, {"favorite_rank": 10})
        call_args = model.predict_proba.call_args[0][0]
        assert call_args["season_progress"].values[0] == 0.5


# ============================================================================
# TESTS: SPREAD COVERAGE SCENARIOS
# ============================================================================

class TestSpreadCoverageScenarios:
    """Integration tests combining spread data, game results, and edge calculations."""

    def test_home_favorite_covers(self):
        """Home favorite covers: wins by more than spread."""
        spread = SpreadFactory.moderate_favorite(home_spread=-7.5)
        result = GameResultFactory.home_comfortable_win(home_score=78, away_score=68)
        margin = result["margin"]  # 10
        assert margin > abs(spread["home_spread"])  # 10 > 7.5 -> covers

    def test_home_favorite_fails_to_cover(self):
        """Home favorite fails to cover: wins but by less than spread."""
        spread = SpreadFactory.moderate_favorite(home_spread=-7.5)
        result = GameResultFactory.home_close_win(home_score=72, away_score=69)
        margin = result["margin"]  # 3
        assert margin < abs(spread["home_spread"])  # 3 < 7.5 -> does NOT cover

    def test_away_underdog_covers_outright_win(self):
        """Away underdog covers by winning outright."""
        spread = SpreadFactory.moderate_favorite(home_spread=-7.5)
        result = GameResultFactory.away_upset(home_score=65, away_score=71)
        # Away team won outright, so they definitely cover +7.5
        assert result["margin"] < 0  # Home lost

    def test_heavy_favorite_back_door_cover(self):
        """Heavy favorite covers late despite close game."""
        spread = SpreadFactory.heavy_favorite(home_spread=-12.5)
        result = GameResultFactory.custom(home_score=80, away_score=66)
        margin = result["margin"]  # 14
        assert margin > abs(spread["home_spread"])  # 14 > 12.5 -> covers

    def test_pick_em_home_win(self):
        """Pick'em game, home team wins."""
        spread = SpreadFactory.pick_em()
        result = GameResultFactory.home_close_win()
        # Any win covers a pick'em spread of 0
        assert result["margin"] > spread["home_spread"]

    def test_over_under_calculation(self):
        """Total points vs over/under line."""
        spread = SpreadFactory.moderate_favorite()
        high_scoring = GameResultFactory.overtime_game()
        low_scoring = GameResultFactory.low_scoring()

        assert high_scoring["total_points"] > spread["over_under"]  # Over hits
        assert low_scoring["total_points"] < spread["over_under"]  # Under hits

    def test_arbitrage_with_spread_data(self):
        """Full arbitrage detection with realistic spread and PM data."""
        from backend.data_collection.arbitrage_detector import detect_arbitrage, american_odds_to_prob

        spread = SpreadFactory.moderate_favorite(home_ml=-280, away_ml=220)
        game = {
            "id": "scenario-1",
            "home_team": "Duke",
            "away_team": "UNC",
            "home_ml": spread["home_ml"],
            "away_ml": spread["away_ml"],
        }

        # Sportsbook implied prob for home ML
        sb_prob = american_odds_to_prob(spread["home_ml"])

        # PM at 0.85 vs sportsbook at ~73.7% -> delta ~11.3%
        pm = PredictionMarketFactory.kalshi_with_edge(
            "scenario-1", "Duke", "UNC",
            home_price=0.85, away_price=0.15,
        )

        result = detect_arbitrage(game, pm, "home_ml")
        assert result is not None
        assert result["is_actionable"] is True
        assert result["delta"] > 10.0

    def test_ev_with_factory_data(self):
        """Calculate EV using factory-generated spread data."""
        from backend.data_collection.arbitrage_detector import calculate_ev, american_odds_to_prob

        spread = SpreadFactory.slight_favorite(home_ml=-155, away_ml=130)
        sb_prob = american_odds_to_prob(spread["home_ml"])

        # Your model estimates 65% for home
        ev = calculate_ev(your_prob=0.65, sportsbook_prob=sb_prob, odds=spread["home_ml"])
        assert ev > 0  # Positive EV since 65% > 60.8%

    def test_kelly_with_factory_data(self):
        """Calculate Kelly stake using factory-generated spread data."""
        from backend.data_collection.arbitrage_detector import get_kelly_stake

        spread = SpreadFactory.slight_favorite(home_ml=-155)
        stake = get_kelly_stake(your_prob=0.65, odds=spread["home_ml"], fraction=0.25)
        assert stake > 0
        assert stake < 0.10  # Quarter Kelly should be conservative

    def test_edge_calculation_matches_factory(self):
        """Edge calculation factory values are mathematically correct."""
        edge_case = EdgeCalculationFactory.clear_edge()
        expected_edge = abs(edge_case["model_prob_home_cover"] - 0.50) * 100
        assert abs(expected_edge - edge_case["expected_edge_pct"]) < 0.1

        edge_case = EdgeCalculationFactory.marginal_edge()
        expected_edge = abs(edge_case["model_prob_home_cover"] - 0.50) * 100
        assert abs(expected_edge - edge_case["expected_edge_pct"]) < 0.1

        edge_case = EdgeCalculationFactory.no_edge()
        expected_edge = abs(edge_case["model_prob_home_cover"] - 0.50) * 100
        assert abs(expected_edge - edge_case["expected_edge_pct"]) < 0.1


# ============================================================================
# TESTS: BREAKEVEN AND ROI CALCULATIONS
# ============================================================================

class TestBreakevenAndROI:
    """Tests for breakeven threshold and ROI calculations."""

    def test_breakeven_at_minus_110(self):
        """Breakeven at -110 odds is 52.38%."""
        from backend.analysis.validate_edge import BREAKEVEN_PCT
        expected = 110 / (110 + 100)
        assert abs(BREAKEVEN_PCT - expected) < 0.001

    def test_roi_calculation_winning(self):
        """ROI is positive when win rate > breakeven."""
        bets_placed = 100
        win_rate = 0.55
        bets_won = int(bets_placed * win_rate)
        bets_lost = bets_placed - bets_won

        profit = (bets_won * 100) - (bets_lost * 110)
        total_wagered = bets_placed * 110
        roi = profit / total_wagered

        assert roi > 0
        # 55% win rate at -110 -> ~4.5% ROI
        assert abs(roi - 0.045) < 0.02

    def test_roi_calculation_losing(self):
        """ROI is negative when win rate < breakeven."""
        bets_placed = 100
        win_rate = 0.45
        bets_won = int(bets_placed * win_rate)
        bets_lost = bets_placed - bets_won

        profit = (bets_won * 100) - (bets_lost * 110)
        total_wagered = bets_placed * 110
        roi = profit / total_wagered

        assert roi < 0

    def test_roi_at_exact_breakeven(self):
        """ROI near zero at breakeven win rate."""
        # Use large sample for precision
        bets_placed = 10000
        bets_won = 5238  # 52.38%
        bets_lost = bets_placed - bets_won

        profit = (bets_won * 100) - (bets_lost * 110)
        total_wagered = bets_placed * 110
        roi = profit / total_wagered

        assert abs(roi) < 0.005  # Should be very close to zero

    def test_vig_free_probabilities(self):
        """Vig-free probabilities should sum to 1.0."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        home_ml = -280
        away_ml = 220

        home_prob = american_odds_to_prob(home_ml)
        away_prob = american_odds_to_prob(away_ml)
        total_prob = home_prob + away_prob

        # Remove vig to get true probabilities
        vig_free_home = home_prob / total_prob
        vig_free_away = away_prob / total_prob

        assert abs(vig_free_home + vig_free_away - 1.0) < 0.001

    def test_implied_overround(self):
        """Overround (vig) calculation from a typical line."""
        from backend.data_collection.arbitrage_detector import american_odds_to_prob

        # Standard -110/-110 has ~4.76% overround
        home_prob = american_odds_to_prob(-110)
        away_prob = american_odds_to_prob(-110)
        overround = (home_prob + away_prob - 1.0) * 100
        assert abs(overround - 4.76) < 0.5

        # Wider line -150/+130 has less overround
        home_prob2 = american_odds_to_prob(-150)
        away_prob2 = american_odds_to_prob(130)
        overround2 = (home_prob2 + away_prob2 - 1.0) * 100
        assert overround2 > 0  # Still has vig


# ============================================================================
# TESTS: FILTER TARGET GAMES
# ============================================================================

class TestFilterTargetGames:
    """Tests for filter_target_games() in validate_edge.py."""

    def test_filter_keeps_target_games(self):
        """Games that match both criteria are kept."""
        from backend.analysis.validate_edge import filter_target_games
        df = pd.DataFrame([
            {"same_conference": True, "ranked_vs_unranked": True, "extra": "kept"},
            {"same_conference": True, "ranked_vs_unranked": False, "extra": "dropped"},
            {"same_conference": False, "ranked_vs_unranked": True, "extra": "dropped"},
            {"same_conference": True, "ranked_vs_unranked": True, "extra": "kept2"},
        ])
        result = filter_target_games(df)
        assert len(result) == 2

    def test_filter_handles_string_booleans(self):
        """Filter handles string 'True'/'False' from CSV loading."""
        from backend.analysis.validate_edge import filter_target_games
        df = pd.DataFrame([
            {"same_conference": "True", "ranked_vs_unranked": "True"},
        ])
        result = filter_target_games(df)
        # String "True" cast to bool is True (non-empty string)
        assert len(result) >= 0  # Should not raise

    def test_filter_empty_dataframe(self):
        """Empty input returns empty output."""
        from backend.analysis.validate_edge import filter_target_games
        df = pd.DataFrame(columns=["same_conference", "ranked_vs_unranked"])
        result = filter_target_games(df)
        assert len(result) == 0


# ============================================================================
# TESTS: ANALYZE BY SPREAD SIZE (TIER BREAKDOWN)
# ============================================================================

class TestAnalyzeBySpreadSize:
    """Tests for analyze_by_spread_size() in validate_edge.py."""

    def test_breakdown_by_tier(self):
        """Results break down correctly by favorite ranking tier."""
        from backend.analysis.validate_edge import analyze_by_spread_size

        results_df = pd.DataFrame([
            {"favorite_rank": 3, "result": "win"},
            {"favorite_rank": 4, "result": "win"},
            {"favorite_rank": 5, "result": "loss"},
            {"favorite_rank": 10, "result": "win"},
            {"favorite_rank": 12, "result": "loss"},
            {"favorite_rank": 20, "result": "win"},
            {"favorite_rank": 22, "result": "loss"},
        ])

        breakdowns = analyze_by_spread_size(results_df)

        assert "Top 5" in breakdowns
        assert breakdowns["Top 5"]["wins"] == 2
        assert breakdowns["Top 5"]["total"] == 3

        assert "6-15" in breakdowns
        assert breakdowns["6-15"]["wins"] == 1
        assert breakdowns["6-15"]["total"] == 2

        assert "16-25" in breakdowns
        assert breakdowns["16-25"]["wins"] == 1
        assert breakdowns["16-25"]["total"] == 2

    def test_breakdown_empty_tier(self):
        """Tiers with no games are excluded."""
        from backend.analysis.validate_edge import analyze_by_spread_size

        results_df = pd.DataFrame([
            {"favorite_rank": 3, "result": "win"},
            {"favorite_rank": 4, "result": "loss"},
        ])

        breakdowns = analyze_by_spread_size(results_df)
        assert "Top 5" in breakdowns
        assert "6-15" not in breakdowns
        assert "16-25" not in breakdowns

    def test_breakdown_excludes_pushes(self):
        """Push results are excluded from tier totals."""
        from backend.analysis.validate_edge import analyze_by_spread_size

        results_df = pd.DataFrame([
            {"favorite_rank": 3, "result": "win"},
            {"favorite_rank": 4, "result": "push"},
            {"favorite_rank": 5, "result": "loss"},
        ])

        breakdowns = analyze_by_spread_size(results_df)
        assert breakdowns["Top 5"]["total"] == 2  # Excludes push

"""
Odds Movement Monitor
=====================

Detects significant betting line movements by comparing current odds
against previously stored spreads. Uses in-memory storage only.

Movement Thresholds:
- Spread: 2.0 points
- Implied probability: 10% (moneyline-derived)
"""

import os
import logging
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

ODDS_API_KEY = os.getenv("ODDS_API_KEY")

# Thresholds for significant movement
SPREAD_MOVEMENT_THRESHOLD = 2.0  # points
PROBABILITY_MOVEMENT_THRESHOLD = 0.10  # 10%


def _ml_to_implied_prob(ml: int) -> float:
    """Convert American moneyline odds to implied probability."""
    if ml > 0:
        return 100.0 / (ml + 100.0)
    elif ml < 0:
        return abs(ml) / (abs(ml) + 100.0)
    return 0.5


class OddsMovement:
    """Represents a detected odds movement for a game."""

    def __init__(
        self,
        game_id: str,
        home_team: str,
        away_team: str,
        previous_spread: Optional[float],
        current_spread: Optional[float],
        previous_home_ml: Optional[int],
        current_home_ml: Optional[int],
        previous_away_ml: Optional[int],
        current_away_ml: Optional[int],
    ):
        self.game_id = game_id
        self.home_team = home_team
        self.away_team = away_team
        self.previous_spread = previous_spread
        self.current_spread = current_spread
        self.previous_home_ml = previous_home_ml
        self.current_home_ml = current_home_ml
        self.previous_away_ml = previous_away_ml
        self.current_away_ml = current_away_ml
        self.detected_at = datetime.now().isoformat()

    @property
    def spread_movement(self) -> Optional[float]:
        if self.previous_spread is not None and self.current_spread is not None:
            return self.current_spread - self.previous_spread
        return None

    @property
    def home_prob_movement(self) -> Optional[float]:
        if self.previous_home_ml is not None and self.current_home_ml is not None:
            prev = _ml_to_implied_prob(self.previous_home_ml)
            curr = _ml_to_implied_prob(self.current_home_ml)
            return curr - prev
        return None

    @property
    def is_significant(self) -> bool:
        spread_mv = self.spread_movement
        if spread_mv is not None and abs(spread_mv) >= SPREAD_MOVEMENT_THRESHOLD:
            return True
        prob_mv = self.home_prob_movement
        if prob_mv is not None and abs(prob_mv) >= PROBABILITY_MOVEMENT_THRESHOLD:
            return True
        return False

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "home_team": self.home_team,
            "away_team": self.away_team,
            "previous_spread": self.previous_spread,
            "current_spread": self.current_spread,
            "spread_movement": self.spread_movement,
            "previous_home_ml": self.previous_home_ml,
            "current_home_ml": self.current_home_ml,
            "previous_away_ml": self.previous_away_ml,
            "current_away_ml": self.current_away_ml,
            "home_prob_movement": round(self.home_prob_movement, 4) if self.home_prob_movement is not None else None,
            "is_significant": self.is_significant,
            "detected_at": self.detected_at,
        }


class OddsMonitor:
    """
    Monitors odds movements using in-memory storage.

    Compares current Odds API data against stored spreads in Supabase
    to detect significant line movements.
    """

    def __init__(self):
        # In-memory cache of current odds keyed by game external_id
        self._current_odds: dict[str, dict] = {}
        self._movements: list[OddsMovement] = []
        self._last_refresh: Optional[str] = None

    def fetch_current_odds(self) -> list[dict]:
        """Fetch current odds from The Odds API."""
        if not ODDS_API_KEY:
            logger.warning("ODDS_API_KEY not configured")
            return []

        url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
        params = {
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "spreads,h2h",
            "oddsFormat": "american",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            self._last_refresh = datetime.now().isoformat()
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching current odds: {e}")
            return []

    def detect_movement(self, current_odds: list[dict]) -> list[OddsMovement]:
        """
        Compare current odds against stored spreads to detect movements.

        Args:
            current_odds: Raw odds data from The Odds API

        Returns:
            List of OddsMovement objects for games with any movement
        """
        from backend.api.supabase_client import get_supabase

        client = get_supabase()
        movements: list[OddsMovement] = []

        for game_data in current_odds:
            home_team = game_data.get("home_team", "")
            away_team = game_data.get("away_team", "")
            external_id = game_data.get("id", "")

            # Extract current spread and ML from first bookmaker
            current_spread = None
            current_home_ml = None
            current_away_ml = None

            for bookmaker in game_data.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") == "spreads" and current_spread is None:
                        for outcome in market.get("outcomes", []):
                            if outcome.get("name") == home_team:
                                current_spread = outcome.get("point")
                    elif market.get("key") == "h2h":
                        for outcome in market.get("outcomes", []):
                            if outcome.get("name") == home_team and current_home_ml is None:
                                current_home_ml = outcome.get("price")
                            elif outcome.get("name") == away_team and current_away_ml is None:
                                current_away_ml = outcome.get("price")
                if current_spread is not None and current_home_ml is not None:
                    break

            # Look up stored spread from database
            # Find game by matching teams (simplified lookup)
            try:
                game_result = client.table("games").select(
                    "id, home_team:home_team_id(name), away_team:away_team_id(name)"
                ).eq("external_id", external_id).limit(1).execute()

                if not game_result.data:
                    continue

                game = game_result.data[0]
                game_id = game["id"]

                # Get latest stored spread
                spread_result = client.table("spreads").select(
                    "home_spread, home_ml, away_ml"
                ).eq("game_id", game_id).order(
                    "captured_at", desc=True
                ).limit(1).execute()

                if not spread_result.data:
                    continue

                stored = spread_result.data[0]
                previous_spread = stored.get("home_spread")
                previous_home_ml = stored.get("home_ml")
                previous_away_ml = stored.get("away_ml")

                movement = OddsMovement(
                    game_id=game_id,
                    home_team=game.get("home_team", {}).get("name", home_team),
                    away_team=game.get("away_team", {}).get("name", away_team),
                    previous_spread=previous_spread,
                    current_spread=current_spread,
                    previous_home_ml=previous_home_ml,
                    current_home_ml=current_home_ml,
                    previous_away_ml=previous_away_ml,
                    current_away_ml=current_away_ml,
                )

                movements.append(movement)

            except Exception as e:
                logger.warning(f"Error checking movement for {home_team} vs {away_team}: {e}")
                continue

        self._movements = movements
        # Update in-memory cache
        for game_data in current_odds:
            self._current_odds[game_data.get("id", "")] = game_data

        return movements

    def check_all_active_games(self) -> dict:
        """
        Fetch current odds and detect movements for all active games.

        Returns:
            Dict with total games checked, movements found, and significant movements
        """
        current_odds = self.fetch_current_odds()
        if not current_odds:
            return {
                "status": "error",
                "message": "Failed to fetch current odds",
                "games_checked": 0,
                "movements": [],
                "significant_movements": [],
            }

        movements = self.detect_movement(current_odds)
        significant = [m for m in movements if m.is_significant]

        return {
            "status": "success",
            "last_refresh": self._last_refresh,
            "games_checked": len(current_odds),
            "total_movements": len(movements),
            "significant_count": len(significant),
            "movements": [m.to_dict() for m in movements],
            "significant_movements": [m.to_dict() for m in significant],
        }

    def get_game_movement(self, game_id: str) -> Optional[dict]:
        """Get movement data for a specific game from the last check."""
        for m in self._movements:
            if m.game_id == game_id:
                return m.to_dict()
        return None


# Global monitor instance
odds_monitor = OddsMonitor()

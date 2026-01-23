"""
Arbitrage Detection Service

Detects arbitrage opportunities between prediction markets and sportsbooks.
Calculates edge as: |prediction_market_prob - sportsbook_implied_prob| * 100
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum delta percentage to flag as actionable
EDGE_THRESHOLD = 10.0


def american_odds_to_prob(odds: Optional[int]) -> float:
    """
    Convert American odds to implied probability.

    Args:
        odds: American odds (e.g., -150, +130)

    Returns:
        Implied probability as decimal (0-1)

    Examples:
        -110 -> 0.524 (52.4%)
        +150 -> 0.40 (40%)
        -150 -> 0.60 (60%)
    """
    if odds is None:
        return 0.5  # Default to 50% if no odds

    if odds < 0:
        # Favorite: |odds| / (|odds| + 100)
        return abs(odds) / (abs(odds) + 100)
    else:
        # Underdog: 100 / (odds + 100)
        return 100 / (odds + 100)


def detect_arbitrage(
    game: dict,
    prediction_market: dict,
    bet_type: str
) -> Optional[dict]:
    """
    Compare prediction market price to sportsbook implied probability.

    Args:
        game: Game data with spreads/ML (home_ml, away_ml, home_spread, etc.)
        prediction_market: Prediction market data with 'outcomes' list
        bet_type: One of 'home_ml', 'away_ml', 'home_spread', 'away_spread'

    Returns:
        Arbitrage opportunity dict if edge detected, else None
    """
    # Get sportsbook implied probability based on bet type
    if bet_type == "home_ml":
        sportsbook_prob = american_odds_to_prob(game.get("home_ml"))
    elif bet_type == "away_ml":
        sportsbook_prob = american_odds_to_prob(game.get("away_ml"))
    elif bet_type in ["home_spread", "away_spread"]:
        # Spread bets are typically -110 both sides = 52.38%
        sportsbook_prob = 0.5238
    else:
        return None

    # Find matching outcome in prediction market
    pm_prob = None
    home_team = game.get("home_team", "").lower()
    away_team = game.get("away_team", "").lower()

    for outcome in prediction_market.get("outcomes", []):
        outcome_name = outcome.get("name", "").lower()
        price = outcome.get("price", 0)

        if bet_type in ["home_ml", "home_spread"]:
            # Looking for home team outcome
            if (home_team and home_team in outcome_name) or outcome_name == "yes":
                pm_prob = price
                break
        elif bet_type in ["away_ml", "away_spread"]:
            # Looking for away team outcome
            if (away_team and away_team in outcome_name) or outcome_name == "no":
                pm_prob = price
                break

    if pm_prob is None:
        return None

    # Calculate delta
    delta = abs(pm_prob - sportsbook_prob) * 100

    # Determine direction of edge
    if pm_prob > sportsbook_prob:
        edge_direction = "prediction_higher"
    else:
        edge_direction = "sportsbook_higher"

    opportunity = {
        "game_id": game.get("id"),
        "prediction_market_id": prediction_market.get("id"),
        "bet_type": bet_type,
        "sportsbook_implied_prob": round(sportsbook_prob, 4),
        "prediction_market_prob": round(pm_prob, 4),
        "delta": round(delta, 3),
        "edge_direction": edge_direction,
        "is_actionable": delta >= EDGE_THRESHOLD
    }

    if opportunity["is_actionable"]:
        logger.info(
            f"Arbitrage detected: {game.get('home_team')} vs {game.get('away_team')} "
            f"- {bet_type} delta {delta:.1f}%"
        )

    return opportunity


async def scan_game_for_arbitrage(
    game: dict,
    markets: list[dict]
) -> list[dict]:
    """
    Scan all prediction markets for a game and find arbitrage opportunities.

    Args:
        game: Game dict with id, home_team, away_team, home_ml, away_ml, etc.
        markets: List of prediction market dicts for this game

    Returns:
        List of arbitrage opportunity dicts
    """
    opportunities = []
    game_id = game.get("id")

    for market in markets:
        # Only look at markets matched to this game
        if market.get("game_id") != game_id:
            continue

        # Check each bet type
        for bet_type in ["home_ml", "away_ml"]:
            opp = detect_arbitrage(game, market, bet_type)
            if opp:
                opportunities.append(opp)

    return opportunities


def calculate_ev(
    your_prob: float,
    sportsbook_prob: float,
    odds: int
) -> float:
    """
    Calculate expected value of a bet.

    Args:
        your_prob: Your estimated probability of winning (0-1)
        sportsbook_prob: Sportsbook implied probability (0-1)
        odds: American odds for the bet

    Returns:
        Expected value as percentage of stake
    """
    if odds < 0:
        # Favorite: win $100 for every $|odds| risked
        payout = 100 / abs(odds)
    else:
        # Underdog: win $odds for every $100 risked
        payout = odds / 100

    # EV = (prob_win * payout) - (prob_lose * stake)
    ev = (your_prob * payout) - ((1 - your_prob) * 1)

    return round(ev * 100, 2)  # Return as percentage


def get_kelly_stake(
    your_prob: float,
    odds: int,
    fraction: float = 0.25
) -> float:
    """
    Calculate Kelly criterion stake size.

    Args:
        your_prob: Your estimated probability of winning (0-1)
        odds: American odds for the bet
        fraction: Kelly fraction (default 0.25 = quarter Kelly for safety)

    Returns:
        Recommended stake as fraction of bankroll
    """
    if odds < 0:
        decimal_odds = 1 + (100 / abs(odds))
    else:
        decimal_odds = 1 + (odds / 100)

    # Kelly formula: f = (bp - q) / b
    # where b = decimal odds - 1, p = prob of winning, q = prob of losing
    b = decimal_odds - 1
    p = your_prob
    q = 1 - p

    kelly = (b * p - q) / b

    # Apply fractional Kelly and ensure non-negative
    stake = max(0, kelly * fraction)

    return round(stake, 4)


# For testing
if __name__ == "__main__":
    # Test American odds conversion
    test_odds = [-110, +150, -150, -200, +200, -300]
    print("American odds to probability:")
    for odds in test_odds:
        prob = american_odds_to_prob(odds)
        print(f"  {odds:+d} -> {prob:.1%}")

    # Test arbitrage detection
    print("\nArbitrage detection test:")
    fake_game = {
        "id": "test-game-1",
        "home_team": "Duke Blue Devils",
        "away_team": "UNC Tar Heels",
        "home_ml": -150,
        "away_ml": +130,
    }

    fake_market = {
        "id": "test-market-1",
        "game_id": "test-game-1",
        "outcomes": [
            {"name": "Duke", "price": 0.70},
            {"name": "UNC", "price": 0.30}
        ]
    }

    for bet_type in ["home_ml", "away_ml"]:
        opp = detect_arbitrage(fake_game, fake_market, bet_type)
        if opp:
            print(f"  {bet_type}: delta={opp['delta']:.1f}%, actionable={opp['is_actionable']}")

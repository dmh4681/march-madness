"""
Bet Results Population Pipeline
================================

This module handles:
1. Fetching final scores for completed games from ESPN
2. Updating game records with final scores
3. Auto-creating pending bet_results from high/medium confidence predictions
4. Grading pending bets (win/loss/push) once scores are available

Bet Grading Logic
=================

**Spread Bets** (bet_type='spread'):
  - spread_at_bet: home team's spread (negative = home is favorite)
  - actual_margin: home_score - away_score

  Side='home' (betting home team covers):
    - Win  if: actual_margin + spread_at_bet > 0
    - Push if: actual_margin + spread_at_bet == 0
    - Loss if: actual_margin + spread_at_bet < 0

  Side='away' (betting away team covers):
    - Win  if: actual_margin + spread_at_bet < 0
    - Push if: actual_margin + spread_at_bet == 0
    - Loss if: actual_margin + spread_at_bet > 0

  Examples:
    Home -7 (spread_at_bet=-7), home wins by 10 (margin=10): 10 + (-7) = 3 > 0 → home WIN
    Home -7 (spread_at_bet=-7), home wins by 3 (margin=3):   3 + (-7) = -4 < 0 → home LOSS
    Home +7 (spread_at_bet=+7), home loses by 5 (margin=-5): -5 + 7 = 2 > 0 → home WIN (covered +7)

**Moneyline Bets** (bet_type='ml'):
  - Side='home': Win if margin > 0, Loss if margin < 0, Push if margin == 0
  - Side='away': Win if margin < 0, Loss if margin > 0, Push if margin == 0

**Payout Calculation** (American odds):
  - Win, negative odds (e.g., -110): units_won = units_wagered * (100 / abs(odds))
  - Win, positive odds (e.g., +130): units_won = units_wagered * (odds / 100)
  - Loss:  units_won = -units_wagered
  - Push:  units_won = 0.0
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

load_dotenv()

logger = logging.getLogger(__name__)

EASTERN_TZ = ZoneInfo("America/New_York")

# ESPN public scoreboard API
ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# Mapping from predictions.recommended_bet → (bet_type, side)
_RECOMMENDED_BET_MAP = {
    "home_spread": {"bet_type": "spread", "side": "home"},
    "away_spread": {"bet_type": "spread", "side": "away"},
    "home_ml":     {"bet_type": "ml",     "side": "home"},
    "away_ml":     {"bet_type": "ml",     "side": "away"},
}


# ============================================
# PURE CALCULATION FUNCTIONS
# ============================================


def calculate_bet_result(
    bet_type: str,
    side: str,
    actual_margin: float,
    spread_at_bet: Optional[float] = None,
) -> str:
    """
    Calculate the result of a bet given the actual game margin.

    Args:
        bet_type: 'spread' or 'ml'
        side: 'home' or 'away'
        actual_margin: home_score - away_score (positive = home team won)
        spread_at_bet: Home team's spread (negative = home is favorite).
                       Required for spread bets.

    Returns:
        'win', 'loss', or 'push'
    """
    if bet_type == "spread":
        if spread_at_bet is None:
            raise ValueError("spread_at_bet is required for spread bets")

        # covered_margin > 0 means the picked side covered
        if side == "home":
            covered_margin = actual_margin + spread_at_bet
        else:  # away
            covered_margin = -(actual_margin + spread_at_bet)

        if covered_margin > 0:
            return "win"
        elif covered_margin < 0:
            return "loss"
        else:
            return "push"

    elif bet_type == "ml":
        if side == "home":
            if actual_margin > 0:
                return "win"
            elif actual_margin < 0:
                return "loss"
            else:
                return "push"
        else:  # away
            if actual_margin < 0:
                return "win"
            elif actual_margin > 0:
                return "loss"
            else:
                return "push"

    else:
        raise ValueError(f"Unsupported bet_type: {bet_type!r}. Expected 'spread' or 'ml'.")


def calculate_units_won(result: str, units_wagered: float, odds_at_bet: int) -> float:
    """
    Calculate net units won/lost for a graded bet.

    Args:
        result: 'win', 'loss', or 'push'
        units_wagered: Amount bet in units (e.g., 1.0)
        odds_at_bet: American odds (e.g., -110, +130)

    Returns:
        Net units won (negative for a loss, 0 for a push)
    """
    if result == "push":
        return 0.0
    elif result == "loss":
        return round(-units_wagered, 4)
    elif result == "win":
        if odds_at_bet < 0:
            # Risk |odds| to win 100
            return round(units_wagered * (100.0 / abs(odds_at_bet)), 4)
        else:
            # Risk 100 to win odds
            return round(units_wagered * (odds_at_bet / 100.0), 4)
    else:
        raise ValueError(f"Unknown result: {result!r}")


# ============================================
# SCORE POPULATION
# ============================================


def fetch_espn_scores_for_date(target_date: date) -> list[dict]:
    """
    Fetch final game scores from ESPN API for a specific date.

    Only returns games with status STATUS_FINAL that have both scores.

    Returns:
        list of dicts with keys:
            espn_id, espn_external_id, home_team, away_team,
            home_score, away_score, status
    """
    date_str = target_date.strftime("%Y%m%d")
    params = {"dates": date_str, "limit": 500}

    try:
        response = requests.get(ESPN_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        games = []
        for event in data.get("events", []):
            try:
                espn_id = event.get("id")
                competitions = event.get("competitions", [])
                if not competitions:
                    continue

                competition = competitions[0]
                status_name = (
                    competition.get("status", {}).get("type", {}).get("name", "")
                )

                # Only process completed games
                if status_name != "STATUS_FINAL":
                    continue

                competitors = competition.get("competitors", [])
                if len(competitors) != 2:
                    continue

                home_team = None
                away_team = None
                home_score = None
                away_score = None

                for competitor in competitors:
                    team_name = competitor.get("team", {}).get("displayName", "")
                    is_home = competitor.get("homeAway") == "home"
                    score_str = competitor.get("score", "")
                    try:
                        score = int(score_str) if score_str else None
                    except (ValueError, TypeError):
                        score = None

                    if is_home:
                        home_team = team_name
                        home_score = score
                    else:
                        away_team = team_name
                        away_score = score

                if (
                    home_team
                    and away_team
                    and home_score is not None
                    and away_score is not None
                ):
                    games.append({
                        "espn_id": espn_id,
                        "espn_external_id": f"espn-{espn_id}",
                        "home_team": home_team,
                        "away_team": away_team,
                        "home_score": home_score,
                        "away_score": away_score,
                        "status": status_name,
                    })

            except Exception as e:
                logger.warning(f"Error parsing ESPN event: {e}")
                continue

        logger.info(f"Fetched {len(games)} final scores from ESPN for {target_date}")
        return games

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching ESPN scores for {target_date}: {e}")
        return []


def populate_game_scores(days_back: int = 3) -> dict:
    """
    Fetch final scores from ESPN and update the games table.

    Looks back `days_back` days for games without scores.
    Matches games by ESPN external_id (e.g., 'espn-401234567').

    Args:
        days_back: Number of past days to scan for missing scores (default 3)

    Returns:
        dict with counts: games_scored, games_already_scored, games_not_found, errors
    """
    from backend.api.supabase_client import get_supabase

    client = get_supabase()
    today = datetime.now(EASTERN_TZ).date()

    results = {
        "games_scored": 0,
        "games_already_scored": 0,
        "games_not_found": 0,
        "errors": 0,
        "error_details": [],
    }

    for day_offset in range(1, days_back + 1):
        target_date = today - timedelta(days=day_offset)

        espn_games = fetch_espn_scores_for_date(target_date)
        if not espn_games:
            logger.info(f"No final scores from ESPN for {target_date}")
            continue

        for espn_game in espn_games:
            try:
                espn_external_id = espn_game["espn_external_id"]

                # Look up game by ESPN external_id
                db_result = client.table("games").select(
                    "id, home_score, away_score, status"
                ).eq("external_id", espn_external_id).execute()

                if not db_result.data:
                    logger.debug(
                        f"No DB game found for {espn_external_id} "
                        f"({espn_game['away_team']} @ {espn_game['home_team']})"
                    )
                    results["games_not_found"] += 1
                    continue

                game = db_result.data[0]
                game_id = game["id"]

                # Skip if already has scores
                if (
                    game.get("home_score") is not None
                    and game.get("away_score") is not None
                ):
                    results["games_already_scored"] += 1
                    continue

                # Update with final scores
                client.table("games").update({
                    "home_score": espn_game["home_score"],
                    "away_score": espn_game["away_score"],
                    "status": "final",
                }).eq("id", game_id).execute()

                results["games_scored"] += 1
                logger.info(
                    f"Scored: {espn_game['away_team']} {espn_game['away_score']} "
                    f"@ {espn_game['home_team']} {espn_game['home_score']}"
                )

            except Exception as e:
                logger.error(
                    f"Error updating score for ESPN game {espn_game.get('espn_id', '?')}: {e}"
                )
                results["errors"] += 1
                results["error_details"].append(str(e)[:100])

    logger.info(f"Score population complete: {results}")
    return results


# ============================================
# PENDING BET CREATION
# ============================================


def auto_create_pending_bets(min_confidence_tier: str = "medium") -> dict:
    """
    Auto-create pending bet_results from high/medium confidence predictions.

    Creates a 'pending' bet_result for each eligible prediction that:
    - Has confidence_tier of 'high' (always) or 'medium' (if min_confidence_tier='medium')
    - Has a recommended_bet that maps to a supported bet type (not 'pass')
    - Does NOT already have a bet_result linked to its prediction_id
    - Corresponds to a game dated today or in the future (no retroactive bets)

    The spread/odds at the time of bet creation are pulled from the most
    recent entry in the spreads table for that game.

    Args:
        min_confidence_tier: 'high' (only high) or 'medium' (high + medium)

    Returns:
        dict with counts: bets_created, bets_skipped, errors
    """
    from backend.api.supabase_client import get_supabase

    client = get_supabase()
    today = datetime.now(EASTERN_TZ).date().isoformat()

    tiers = ["high"]
    if min_confidence_tier == "medium":
        tiers.append("medium")

    results = {
        "bets_created": 0,
        "bets_skipped": 0,
        "errors": 0,
    }

    # Fetch high/medium predictions with actionable recommendations
    pred_result = client.table("predictions").select(
        "id, game_id, recommended_bet, confidence_tier, spread_at_prediction"
    ).in_("confidence_tier", tiers).neq("recommended_bet", "pass").execute()

    if not pred_result.data:
        logger.info("No high/medium confidence predictions found")
        return results

    predictions = pred_result.data
    game_ids = list({p["game_id"] for p in predictions})
    pred_ids = [p["id"] for p in predictions]

    # Filter to games that are today or in the future (don't retroactively create bets)
    games_result = client.table("games").select(
        "id, date, status"
    ).in_("id", game_ids).gte("date", today).execute()
    eligible_game_ids = {g["id"] for g in games_result.data}

    # Find predictions that already have a bet_result
    existing_result = client.table("bet_results").select(
        "prediction_id"
    ).in_("prediction_id", pred_ids).execute()
    already_has_bet = {r["prediction_id"] for r in existing_result.data}

    # Get latest spread data for each eligible game (for odds lookup)
    spread_result = client.table("spreads").select(
        "game_id, home_spread, home_spread_odds, away_spread_odds, home_ml, away_ml"
    ).in_("game_id", list(eligible_game_ids)).order("captured_at", desc=True).execute()

    # Build spread map: game_id → most recent spread row
    spread_map: dict = {}
    for s in spread_result.data:
        if s["game_id"] not in spread_map:
            spread_map[s["game_id"]] = s

    for pred in predictions:
        pred_id = pred["id"]
        game_id = pred["game_id"]

        if game_id not in eligible_game_ids:
            results["bets_skipped"] += 1
            continue

        if pred_id in already_has_bet:
            results["bets_skipped"] += 1
            continue

        bet_fields = _RECOMMENDED_BET_MAP.get(pred["recommended_bet"])
        if not bet_fields:
            results["bets_skipped"] += 1
            continue

        try:
            spread_data = spread_map.get(game_id, {})
            spread_at_bet = pred.get("spread_at_prediction")

            # Look up appropriate odds based on bet type/side
            if bet_fields["bet_type"] == "spread":
                if bet_fields["side"] == "home":
                    odds_at_bet = spread_data.get("home_spread_odds", -110) or -110
                else:
                    odds_at_bet = spread_data.get("away_spread_odds", -110) or -110
            elif bet_fields["bet_type"] == "ml":
                if bet_fields["side"] == "home":
                    odds_at_bet = spread_data.get("home_ml", -110) or -110
                else:
                    odds_at_bet = spread_data.get("away_ml", -110) or -110
            else:
                odds_at_bet = -110

            bet_data = {
                "prediction_id": pred_id,
                "game_id": game_id,
                "bet_type": bet_fields["bet_type"],
                "side": bet_fields["side"],
                "spread_at_bet": spread_at_bet,
                "odds_at_bet": int(odds_at_bet),
                "result": "pending",
                "units_wagered": 1.0,
            }

            client.table("bet_results").insert(bet_data).execute()
            results["bets_created"] += 1
            logger.debug(
                f"Created pending bet: {pred['recommended_bet']} "
                f"({pred['confidence_tier']}) for game {game_id[:8]}"
            )

        except Exception as e:
            logger.error(f"Error creating bet for prediction {pred_id}: {e}")
            results["errors"] += 1

    logger.info(f"Auto-create pending bets complete: {results}")
    return results


# ============================================
# BET GRADING
# ============================================


def grade_pending_bets() -> dict:
    """
    Grade all pending bets where the game now has final scores.

    For each pending bet_result:
    1. Check if the linked game has home_score and away_score
    2. If yes, calculate actual_margin = home_score - away_score
    3. Determine win/loss/push using calculate_bet_result()
    4. Calculate units_won using calculate_units_won()
    5. Update bet_results row with result, actual_margin, units_won, graded_at

    Returns:
        dict with counts: bets_graded, bets_still_pending, wins, losses, pushes, errors
    """
    from backend.api.supabase_client import get_supabase

    client = get_supabase()

    results = {
        "bets_graded": 0,
        "bets_still_pending": 0,
        "wins": 0,
        "losses": 0,
        "pushes": 0,
        "errors": 0,
        "error_details": [],
    }

    # Fetch all pending bets with joined game scores
    pending_result = client.table("bet_results").select(
        "id, game_id, bet_type, side, spread_at_bet, odds_at_bet, units_wagered, "
        "game:games(home_score, away_score, status)"
    ).eq("result", "pending").execute()

    if not pending_result.data:
        logger.info("No pending bets to grade")
        return results

    logger.info(f"Found {len(pending_result.data)} pending bets to check")

    for bet in pending_result.data:
        try:
            game = bet.get("game") or {}
            home_score = game.get("home_score")
            away_score = game.get("away_score")

            # Skip if game doesn't have final scores yet
            if home_score is None or away_score is None:
                results["bets_still_pending"] += 1
                continue

            actual_margin = int(home_score) - int(away_score)

            # Grade the bet
            bet_result = calculate_bet_result(
                bet_type=bet["bet_type"],
                side=bet["side"],
                actual_margin=float(actual_margin),
                spread_at_bet=(
                    float(bet["spread_at_bet"])
                    if bet.get("spread_at_bet") is not None
                    else None
                ),
            )

            # Calculate payout
            units_wagered = float(bet.get("units_wagered") or 1.0)
            odds_at_bet = int(bet.get("odds_at_bet") or -110)
            units_won = calculate_units_won(bet_result, units_wagered, odds_at_bet)

            # Persist the graded result
            client.table("bet_results").update({
                "result": bet_result,
                "actual_margin": actual_margin,
                "units_won": units_won,
                "graded_at": datetime.now().isoformat(),
            }).eq("id", bet["id"]).execute()

            results["bets_graded"] += 1
            results[f"{bet_result}s"] += 1
            logger.info(
                f"Graded bet {bet['id'][:8]}: {bet['bet_type']} {bet['side']} "
                f"margin={actual_margin:+d} → {bet_result} ({units_won:+.2f}u)"
            )

        except Exception as e:
            logger.error(f"Error grading bet {bet.get('id', '?')}: {e}")
            results["errors"] += 1
            results["error_details"].append(str(e)[:100])

    logger.info(f"Bet grading complete: {results}")
    return results


# ============================================
# PIPELINE ORCHESTRATION
# ============================================


def run_bet_results_pipeline(
    days_back: int = 3,
    min_confidence_tier: str = "medium",
) -> dict:
    """
    Run the full bet results population pipeline.

    Steps:
    1. Populate final scores for recently completed games (from ESPN)
    2. Auto-create 'pending' bet_results from today's high/medium predictions
    3. Grade pending bets where game scores are now available

    Args:
        days_back: How many past days to scan for missing scores (default 3)
        min_confidence_tier: Minimum confidence tier for auto-creating bets
                             ('high' or 'medium', default 'medium')

    Returns:
        dict with results from each step: scores, pending_bets, grading
    """
    logger.info("=== Running Bet Results Population Pipeline ===")

    results = {}

    # Step 1: Populate game scores from ESPN
    try:
        score_results = populate_game_scores(days_back=days_back)
        results["scores"] = score_results
        logger.info(
            f"Scores: {score_results['games_scored']} updated, "
            f"{score_results['games_not_found']} not found in DB"
        )
    except Exception as e:
        logger.error(f"Score population error: {e}")
        results["scores"] = {"error": str(e)}

    # Step 2: Auto-create pending bets for today's eligible predictions
    try:
        pending_results = auto_create_pending_bets(min_confidence_tier=min_confidence_tier)
        results["pending_bets"] = pending_results
        logger.info(f"Pending bets: {pending_results['bets_created']} created")
    except Exception as e:
        logger.error(f"Pending bet creation error: {e}")
        results["pending_bets"] = {"error": str(e)}

    # Step 3: Grade pending bets (requires scores from step 1)
    try:
        grading_results = grade_pending_bets()
        results["grading"] = grading_results
        logger.info(
            f"Grading: {grading_results['bets_graded']} graded "
            f"({grading_results['wins']}W / "
            f"{grading_results['losses']}L / "
            f"{grading_results['pushes']}P)"
        )
    except Exception as e:
        logger.error(f"Bet grading error: {e}")
        results["grading"] = {"error": str(e)}

    return results


if __name__ == "__main__":
    import json
    import logging as _logging

    _logging.basicConfig(level=_logging.INFO)
    results = run_bet_results_pipeline()
    print("\nResults:")
    print(json.dumps(results, indent=2))

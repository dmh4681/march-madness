"""
Prediction Market Scraper

Main service for scraping and processing prediction market data.
Fetches from Polymarket and Kalshi, matches to games/teams, and detects arbitrage.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


async def refresh_prediction_markets() -> dict:
    """
    Fetch latest prediction market data from all sources.

    Pipeline:
    1. Fetch markets from Polymarket and Kalshi
    2. Match markets to games and teams in our database
    3. Store market data
    4. Detect and store arbitrage opportunities

    Returns:
        Dict with results from each step
    """
    # Import here to avoid circular imports
    from .polymarket_client import PolymarketClient
    from .kalshi_client import KalshiClient
    from .market_matcher import match_market_to_game, match_market_to_team
    from .arbitrage_detector import scan_game_for_arbitrage

    from backend.api.supabase_client import get_supabase

    logger.info("Starting prediction market refresh")

    try:
        supabase = get_supabase()
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        return {"status": "error", "error": str(e)}

    # Get reference data from database
    # Get upcoming games (next 14 days for futures matching)
    try:
        games_resp = supabase.table("upcoming_games").select("*").execute()
        games = games_resp.data or []
    except Exception:
        # Fallback to games table if view doesn't exist
        from datetime import date
        today = date.today().isoformat()
        end_date = (date.today() + timedelta(days=14)).isoformat()
        games_resp = supabase.table("games").select(
            "id, date, home_team_id, away_team_id"
        ).gte("date", today).lte("date", end_date).execute()
        games = games_resp.data or []

    # Get all teams
    teams_resp = supabase.table("teams").select("id, name, normalized_name").execute()
    teams = teams_resp.data or []

    logger.info(f"Reference data: {len(games)} games, {len(teams)} teams")

    results = {
        "polymarket": {"fetched": 0, "matched": 0, "stored": 0},
        "kalshi": {"fetched": 0, "matched": 0, "stored": 0},
        "arbitrage": {"detected": 0, "actionable": 0}
    }

    all_markets = []

    # -------------------------------------------------------------------------
    # 1. Fetch from Polymarket
    # -------------------------------------------------------------------------
    poly_client = PolymarketClient()
    try:
        poly_markets_raw = await poly_client.get_college_basketball_markets()
        results["polymarket"]["fetched"] = len(poly_markets_raw)

        for raw in poly_markets_raw:
            try:
                market = poly_client.parse_market(raw)

                # Try to match to game
                game_id = await match_market_to_game(market, games, teams)

                # Try to match to team (for futures)
                team_id = None
                if not game_id:
                    team_id = await match_market_to_team(market, teams)

                if game_id or team_id:
                    results["polymarket"]["matched"] += 1
                    market["game_id"] = game_id
                    market["team_id"] = team_id

                    # Upsert to database
                    try:
                        supabase.table("prediction_markets").upsert(
                            market, on_conflict="source,market_id"
                        ).execute()
                        results["polymarket"]["stored"] += 1
                        all_markets.append({**market, "id": market["market_id"]})
                    except Exception as e:
                        logger.warning(f"Failed to store Polymarket market: {e}")

            except Exception as e:
                logger.warning(f"Error processing Polymarket market: {e}")
                continue

    except Exception as e:
        logger.error(f"Polymarket fetch failed: {e}")
        results["polymarket"]["error"] = str(e)
    finally:
        await poly_client.close()

    # -------------------------------------------------------------------------
    # 2. Fetch from Kalshi
    # -------------------------------------------------------------------------
    kalshi_client = KalshiClient()
    try:
        if kalshi_client.is_configured:
            kalshi_markets_raw = await kalshi_client.get_college_basketball_markets()
            results["kalshi"]["fetched"] = len(kalshi_markets_raw)

            for raw in kalshi_markets_raw:
                try:
                    market = kalshi_client.parse_market(raw)

                    # Try to match to game
                    game_id = await match_market_to_game(market, games, teams)

                    # Try to match to team (for futures)
                    team_id = None
                    if not game_id:
                        team_id = await match_market_to_team(market, teams)

                    if game_id or team_id:
                        results["kalshi"]["matched"] += 1
                        market["game_id"] = game_id
                        market["team_id"] = team_id

                        # Upsert to database
                        try:
                            supabase.table("prediction_markets").upsert(
                                market, on_conflict="source,market_id"
                            ).execute()
                            results["kalshi"]["stored"] += 1
                            all_markets.append({**market, "id": market["market_id"]})
                        except Exception as e:
                            logger.warning(f"Failed to store Kalshi market: {e}")

                except Exception as e:
                    logger.warning(f"Error processing Kalshi market: {e}")
                    continue
        else:
            logger.info("Kalshi not configured, skipping")
            results["kalshi"]["status"] = "not_configured"

    except Exception as e:
        logger.error(f"Kalshi fetch failed: {e}")
        results["kalshi"]["error"] = str(e)
    finally:
        await kalshi_client.close()

    # -------------------------------------------------------------------------
    # 3. Detect arbitrage for games with prediction data
    # -------------------------------------------------------------------------
    # Get fresh game data with spreads
    try:
        games_with_spreads_resp = supabase.table("today_games").select("*").execute()
        games_with_spreads = games_with_spreads_resp.data or []
    except Exception:
        # Fallback
        games_with_spreads = games

    # Get all stored prediction markets
    try:
        stored_markets_resp = supabase.table("prediction_markets").select("*").eq(
            "status", "open"
        ).execute()
        stored_markets = stored_markets_resp.data or []
    except Exception as e:
        logger.warning(f"Could not fetch stored markets for arbitrage: {e}")
        stored_markets = []

    for game in games_with_spreads:
        try:
            opportunities = await scan_game_for_arbitrage(game, stored_markets)

            for opp in opportunities:
                results["arbitrage"]["detected"] += 1
                if opp.get("is_actionable"):
                    results["arbitrage"]["actionable"] += 1

                # Store opportunity
                try:
                    supabase.table("arbitrage_opportunities").insert(opp).execute()
                except Exception as e:
                    logger.warning(f"Failed to store arbitrage opportunity: {e}")

        except Exception as e:
            logger.warning(f"Error detecting arbitrage for game {game.get('id')}: {e}")
            continue

    # Log summary
    logger.info(
        f"Prediction market refresh complete: "
        f"Polymarket {results['polymarket']['matched']}/{results['polymarket']['fetched']} matched, "
        f"Kalshi {results['kalshi']['matched']}/{results['kalshi']['fetched']} matched, "
        f"Arbitrage {results['arbitrage']['actionable']}/{results['arbitrage']['detected']} actionable"
    )

    results["status"] = "success"
    results["timestamp"] = datetime.now().isoformat()

    return results


def run_sync():
    """Run the prediction market refresh synchronously."""
    return asyncio.run(refresh_prediction_markets())


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    results = run_sync()
    print(json.dumps(results, indent=2))

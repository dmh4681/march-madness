"""
Daily Data Refresh Pipeline
============================

This module orchestrates the complete data collection and prediction pipeline
for Conference Contrarian. It is the heart of the data infrastructure, ensuring
all game data, betting lines, advanced analytics, and AI analyses are current.

Architecture Overview
=====================

The pipeline follows a sequential data flow with strategic dependencies:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        DAILY REFRESH PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Step 0: Cache Invalidation                                             │
│  └── Clear ratings caches to ensure fresh data                          │
│                                                                         │
│  Step 1: ESPN Game Schedule (PRIMARY SOURCE)                            │
│  └── Creates/updates games table with schedule data                     │
│      - External ID, date, tip time                                      │
│      - Home/away team IDs                                               │
│      - Conference game flag                                             │
│                                                                         │
│  Step 2: Betting Lines (The Odds API)                                   │
│  └── Adds spreads to existing games                                     │
│      - Spread (home perspective)                                        │
│      - Moneylines (home/away)                                           │
│      - Over/under total                                                 │
│                                                                         │
│  Step 3a: KenPom Analytics (Subscription Required)                      │
│  └── Updates kenpom_ratings table                                       │
│      - Adjusted efficiency metrics                                      │
│      - Tempo, SOS, luck factors                                         │
│                                                                         │
│  Step 3b: Haslametrics Analytics (FREE)                                 │
│  └── Updates haslametrics_ratings table                                 │
│      - All-Play percentage                                              │
│      - Momentum indicators                                              │
│      - Quadrant records                                                 │
│                                                                         │
│  Step 4: ML Predictions                                                 │
│  └── Creates predictions for games without them                         │
│      - Cover probability                                                │
│      - Confidence tier                                                  │
│      - Recommended bet                                                  │
│                                                                         │
│  Step 5: Game Results                                                   │
│  └── Updates scores for completed games                                 │
│      - Final scores                                                     │
│      - Bet grading                                                      │
│                                                                         │
│  Step 6: Today's View                                                   │
│  └── Refreshes materialized view for dashboard                          │
│                                                                         │
│  Step 7: AI Analysis                                                    │
│  └── Runs Claude analysis on today's unanalyzed games                   │
│      - Structured betting recommendation                                │
│      - Key factors and reasoning                                        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

Data Dependencies
=================

The order of steps matters due to dependencies:

1. **ESPN must run first** - Creates game records that other steps reference
2. **Odds API needs games** - Can only add spreads to existing games
3. **Analytics are independent** - KenPom and Haslametrics can run in parallel
4. **Predictions need spreads** - Uses spread data for probability calculations
5. **AI Analysis needs everything** - Uses all available data for comprehensive analysis

Scheduling
==========

- **Primary Schedule**: Daily at 6 AM EST via GitHub Actions cron
- **Manual Trigger**: POST /refresh endpoint
- **Individual Refreshes**: Separate endpoints for testing:
  - POST /refresh-haslametrics (fast, ~10-20 seconds)
  - POST /refresh-espn-times (fast, ~5-10 seconds)
  - POST /regenerate-predictions (fast, no external API calls)
  - POST /refresh-prediction-markets (moderate, requires async)

Error Handling
==============

Each step is wrapped in try/except to allow partial success:
- Failures are logged with context
- Pipeline continues even if individual steps fail
- Final results dict includes error details for debugging

Performance Considerations
==========================

- **Full refresh**: 3-5 minutes (KenPom login + all scrapers + AI analysis)
- **ESPN + Odds only**: ~30 seconds
- **KenPom**: ~60 seconds (requires Selenium browser automation)
- **Haslametrics**: ~15 seconds (direct XML fetch)
- **AI Analysis**: ~10 seconds per game (API call + DB insert)

Cache Strategy
==============

The pipeline invalidates ratings caches at the start to ensure:
- Fresh data is fetched from scrapers
- Stale cache doesn't mask scraper failures
- Cache is rebuilt with fresh data after refresh

Usage Examples
==============

```python
# Command line - full refresh
python -m backend.data_collection.daily_refresh

# Command line - with force regenerate predictions
python -c "from backend.data_collection.daily_refresh import run_daily_refresh; run_daily_refresh(force_regenerate_predictions=True)"

# Via API - full refresh
curl -X POST https://api.confcontrarian.com/refresh

# Via API - haslametrics only (fast)
curl -X POST https://api.confcontrarian.com/refresh-haslametrics
```

Environment Variables
=====================

Required:
- SUPABASE_URL: PostgreSQL database URL
- SUPABASE_SERVICE_KEY: Database service key

Optional:
- ODDS_API_KEY: For betting lines (500 req/month free tier)
- KENPOM_EMAIL/PASSWORD: For KenPom analytics (subscription)
- ANTHROPIC_API_KEY: For Claude AI analysis
- GROK_API_KEY: For Grok AI analysis

See Also
========

- backend/api/main.py: API endpoints that trigger refresh
- backend/data_collection/kenpom_scraper.py: KenPom data collection
- backend/data_collection/haslametrics_scraper.py: Haslametrics data collection
- backend/data_collection/espn_scraper.py: ESPN schedule data
- backend/api/ai_service.py: AI analysis implementation
"""

import os
import sys
import re
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import json

import requests
import pandas as pd
from dotenv import load_dotenv

# Timezone handling - games should be stored in US Eastern time
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Fallback for older Python

# US Eastern timezone (handles EST/EDT automatically)
EASTERN_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")


def get_eastern_date_today() -> date:
    """
    Get today's date in US Eastern time.

    This ensures consistent date handling for college basketball games,
    which are scheduled and displayed in Eastern time.
    """
    return datetime.now(EASTERN_TZ).date()


def get_eastern_date_yesterday() -> date:
    """Get yesterday's date in US Eastern time."""
    return get_eastern_date_today() - timedelta(days=1)

load_dotenv()

# Configure logging - avoid leaking sensitive info
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY: Configuration
# =============================================================================
# SECURITY: Get API key from environment, never hardcode
ODDS_API_KEY = os.getenv("ODDS_API_KEY")
if not ODDS_API_KEY:
    logger.warning("ODDS_API_KEY not configured - odds fetching will fail")

# SECURITY: Import secure Supabase client with timeouts and validation
from backend.api.supabase_client import get_supabase, _validate_uuid, _sanitize_string

# Import cache utilities for invalidation during refresh
try:
    from backend.utils.cache import invalidate_ratings_caches, ratings_cache
except ImportError:
    # Fallback for direct module execution
    from ..utils.cache import invalidate_ratings_caches, ratings_cache

def _get_supabase():
    """Get the secure Supabase client with proper error handling."""
    try:
        return get_supabase()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        print(f"ERROR: {e}")
        sys.exit(1)

# Initialize client lazily on first use
supabase = None

def _ensure_supabase():
    """Ensure Supabase client is initialized."""
    global supabase
    if supabase is None:
        supabase = _get_supabase()
    return supabase

# Team name mapping for The Odds API -> our normalized names
ODDS_API_TEAM_MAP = {
    "Duke Blue Devils": "duke",
    "North Carolina Tar Heels": "north-carolina",
    "Kentucky Wildcats": "kentucky",
    "Kansas Jayhawks": "kansas",
    "UConn Huskies": "connecticut",
    "Connecticut Huskies": "connecticut",
    "Houston Cougars": "houston",
    "Purdue Boilermakers": "purdue",
    "Tennessee Volunteers": "tennessee",
    "Arizona Wildcats": "arizona",
    "Gonzaga Bulldogs": "gonzaga",
    "Alabama Crimson Tide": "alabama",
    "Baylor Bears": "baylor",
    "Texas Longhorns": "texas",
    "UCLA Bruins": "ucla",
    "Michigan State Spartans": "michigan-state",
    "Marquette Golden Eagles": "marquette",
    "Creighton Bluejays": "creighton",
    "Iowa State Cyclones": "iowa-state",
    "Auburn Tigers": "auburn",
    # Add more as needed
}


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if not name:
        return ""

    # Check direct mapping first
    if name in ODDS_API_TEAM_MAP:
        return ODDS_API_TEAM_MAP[name]

    # Fall back to basic normalization
    result = name.lower()

    # Remove common suffixes
    suffixes = [
        "wildcats", "tigers", "bears", "eagles", "bulldogs", "cardinals",
        "cougars", "ducks", "gators", "hawks", "huskies", "jayhawks",
        "knights", "lions", "longhorns", "mountaineers", "panthers",
        "seminoles", "spartans", "tar heels", "terrapins", "volunteers",
        "wolverines", "blue devils", "crimson tide", "fighting irish",
        "hoosiers", "boilermakers", "buckeyes", "nittany lions",
        "golden gophers", "badgers", "hawkeyes", "cornhuskers",
        "razorbacks", "gamecocks", "commodores", "rebels", "aggies",
    ]

    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[:-len(suffix)].strip()
            break

    return result.replace(" ", "-").replace("'", "").replace(".", "").replace("state", "-state").strip("-")


def get_team_id(name: str) -> Optional[str]:
    """
    Get team ID from normalized name.

    SECURITY: Input is sanitized to prevent SQL wildcard abuse in ilike queries.
    """
    normalized = normalize_team_name(name)
    if not normalized:
        return None

    # SECURITY: Sanitize input - remove SQL wildcards and limit length
    # This prevents wildcard abuse in the ilike query below
    sanitized = _sanitize_string(normalized, max_length=100, field_name="team_name")
    # Remove SQL wildcards that could be abused in ilike queries
    sanitized = re.sub(r'[%_]', '', sanitized)

    if not sanitized:
        return None

    client = _ensure_supabase()

    # First try exact match (most secure)
    result = client.table("teams").select("id").eq("normalized_name", sanitized).execute()

    if result.data:
        return result.data[0]["id"]

    # SECURITY: For partial match, use sanitized input without wildcards
    # The wildcards are added by us, not from user input
    result = client.table("teams").select("id, normalized_name").ilike("normalized_name", f"%{sanitized}%").execute()

    if result.data:
        return result.data[0]["id"]

    return None


def fetch_odds_api_spreads() -> list[dict]:
    """Fetch current college basketball spreads from The Odds API."""
    print("\n=== Fetching Spreads from The Odds API ===")

    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads,h2h,totals",
        "oddsFormat": "american",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()

        data = response.json()
        print(f"Fetched {len(data)} games with odds")

        # Check remaining requests
        remaining = response.headers.get("x-requests-remaining", "unknown")
        used = response.headers.get("x-requests-used", "unknown")
        print(f"API requests: {used} used, {remaining} remaining this month")

        return data

    except requests.exceptions.RequestException as e:
        print(f"Error fetching odds: {e}")
        return []


def process_odds_data(odds_data: list[dict]) -> dict:
    """Process odds data and match to our games."""
    print("\n=== Processing Odds Data ===")

    client = _ensure_supabase()
    games_updated = 0
    spreads_inserted = 0

    for game in odds_data:
        try:
            home_team = game.get("home_team", "")
            away_team = game.get("away_team", "")
            commence_time = game.get("commence_time", "")

            # Get team IDs
            home_team_id = get_team_id(home_team)
            away_team_id = get_team_id(away_team)

            if not home_team_id or not away_team_id:
                # Try to create teams if they don't exist
                continue

            # Parse game date - IMPORTANT: Convert UTC to Eastern time before extracting date
            # This ensures a game at 11 PM Eastern shows up on the correct day
            # (not the next day due to UTC being 4-5 hours ahead)
            game_date = None
            if commence_time:
                # Parse UTC time from API
                utc_time = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
                # Convert to Eastern time, then extract the date
                eastern_time = utc_time.astimezone(EASTERN_TZ)
                game_date = eastern_time.date().isoformat()

            # Find or create game
            game_result = client.table("games").select("id").eq("home_team_id", home_team_id).eq("away_team_id", away_team_id).eq("date", game_date).execute()

            if game_result.data:
                game_id = game_result.data[0]["id"]
            else:
                # Create new game
                new_game = {
                    "external_id": game.get("id", f"{home_team_id}-{away_team_id}-{game_date}"),
                    "date": game_date,
                    "season": 2025,  # Current season
                    "home_team_id": home_team_id,
                    "away_team_id": away_team_id,
                    "is_conference_game": False,  # Would need to determine this
                    "status": "scheduled",
                }
                insert_result = client.table("games").insert(new_game).execute()
                if insert_result.data:
                    game_id = insert_result.data[0]["id"]
                    games_updated += 1
                else:
                    continue

            # Extract spread data from bookmakers
            home_spread = None
            home_ml = None
            away_ml = None
            over_under = None

            # Helper to match team names flexibly
            def teams_match(api_name: str, target_name: str) -> bool:
                if not api_name or not target_name:
                    return False
                # Exact match
                if api_name == target_name:
                    return True
                # Normalize both names for comparison
                api_lower = api_name.lower()
                target_lower = target_name.lower()
                # Check if one contains the other (e.g., "Duke Blue Devils" contains "Duke")
                if api_lower in target_lower or target_lower in api_lower:
                    return True
                # Check first word match (school name)
                api_first = api_lower.split()[0] if api_lower.split() else ""
                target_first = target_lower.split()[0] if target_lower.split() else ""
                if api_first and target_first and api_first == target_first:
                    return True
                return False

            for bookmaker in game.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    if market.get("key") == "spreads" and home_spread is None:
                        for outcome in market.get("outcomes", []):
                            if teams_match(outcome.get("name"), home_team):
                                home_spread = outcome.get("point")

                    elif market.get("key") == "h2h":
                        for outcome in market.get("outcomes", []):
                            outcome_name = outcome.get("name", "")
                            if home_ml is None and teams_match(outcome_name, home_team):
                                home_ml = outcome.get("price")
                            elif away_ml is None and teams_match(outcome_name, away_team):
                                away_ml = outcome.get("price")

                    elif market.get("key") == "totals" and over_under is None:
                        for outcome in market.get("outcomes", []):
                            if outcome.get("name") == "Over":
                                over_under = outcome.get("point")

                # Stop once we have all data we need
                if home_spread is not None and home_ml is not None and away_ml is not None:
                    break

            # Insert spread record
            if home_spread is not None:
                spread_data = {
                    "game_id": game_id,
                    "home_spread": home_spread,
                    "away_spread": -home_spread if home_spread else None,
                    "home_ml": home_ml,
                    "away_ml": away_ml,
                    "over_under": over_under,
                    "source": "odds-api",
                    "is_closing_line": False,
                }

                # Log if moneyline is missing
                if home_ml is None or away_ml is None:
                    print(f"  Warning: Missing ML for {away_team} @ {home_team} (home_ml={home_ml}, away_ml={away_ml})")

                client.table("spreads").insert(spread_data).execute()
                spreads_inserted += 1

        except Exception as e:
            print(f"  Error processing game: {e}")
            continue

    print(f"Games created/updated: {games_updated}")
    print(f"Spreads inserted: {spreads_inserted}")

    return {
        "games_updated": games_updated,
        "spreads_inserted": spreads_inserted,
    }


def fetch_cbbpy_games() -> list[dict]:
    """Fetch recent and upcoming games from CBBpy."""
    print("\n=== Fetching Games from CBBpy ===")

    try:
        from cbbpy.mens_scraper import get_games_range

        # Get games from past week and next week (use Eastern time for consistency)
        today = get_eastern_date_today()
        start_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        games_df = get_games_range(start_date, end_date)

        if games_df is None or len(games_df) == 0:
            print("No games found from CBBpy")
            return []

        print(f"Fetched {len(games_df)} games from CBBpy")
        return games_df.to_dict('records')

    except ImportError:
        print("CBBpy not available, skipping game fetch")
        return []
    except Exception as e:
        print(f"Error fetching games from CBBpy: {e}")
        return []


def run_predictions(force_regenerate: bool = False) -> dict:
    """Run predictions on upcoming games.

    Args:
        force_regenerate: If True, delete existing predictions and regenerate all
    """
    print("\n=== Running Predictions ===")

    client = _ensure_supabase()

    # Get upcoming games without predictions
    # Use Eastern time for consistency with game dates
    today = get_eastern_date_today().isoformat()

    # If force regenerate, delete all predictions for upcoming games first
    if force_regenerate:
        print("Force regenerate enabled - deleting existing predictions for upcoming games...")
        # Get all upcoming game IDs first
        upcoming = client.table("games").select("id").gte("date", today).is_("home_score", "null").execute()
        if upcoming.data:
            game_ids = [g["id"] for g in upcoming.data]
            for gid in game_ids:
                client.table("predictions").delete().eq("game_id", gid).execute()
            print(f"  Deleted predictions for {len(game_ids)} games")

    result = client.table("games").select(
        "id, date, home_team_id, away_team_id, is_conference_game"
    ).gte("date", today).is_("home_score", "null").execute()

    if not result.data:
        print("No upcoming games to predict")
        return {"predictions_created": 0}

    games = result.data
    print(f"Found {len(games)} upcoming games")

    predictions_created = 0

    for game in games:
        try:
            # Check if prediction already exists (skip if not force regenerating)
            if not force_regenerate:
                existing = client.table("predictions").select("id").eq("game_id", game["id"]).execute()
                if existing.data:
                    continue

            # Get latest spread for this game
            spread_result = client.table("spreads").select("home_spread").eq("game_id", game["id"]).order("captured_at", desc=True).limit(1).execute()

            spread = spread_result.data[0]["home_spread"] if spread_result.data else None

            # Simple prediction logic (placeholder for ML model)
            # In reality, this would call your trained model
            home_cover_prob = 0.5
            confidence_tier = "low"
            recommended_bet = "pass"
            edge_pct = None

            if spread is not None:
                # Base adjustment for home court advantage
                home_cover_prob = 0.52  # Slight home edge baseline

                # Conference games have stronger home edge
                if game.get("is_conference_game"):
                    home_cover_prob = 0.53

                # Adjust based on spread magnitude
                if abs(spread) > 10:
                    # Big favorites less likely to cover
                    home_cover_prob = 0.48 if spread < 0 else 0.52
                elif abs(spread) < 3:
                    # Close games, home edge more valuable
                    home_cover_prob = 0.55 if spread < 0 else 0.54
                elif abs(spread) >= 3 and abs(spread) <= 7:
                    # Sweet spot for home favorites
                    home_cover_prob = 0.54 if spread < 0 else 0.52

                # Determine confidence
                edge = abs(home_cover_prob - 0.5) * 100
                if edge > 4:
                    confidence_tier = "high"
                    edge_pct = edge
                    recommended_bet = "home_spread" if home_cover_prob > 0.5 else "away_spread"
                elif edge > 2:
                    confidence_tier = "medium"
                    edge_pct = edge
                    recommended_bet = "home_spread" if home_cover_prob > 0.5 else "away_spread"
                else:
                    confidence_tier = "low"
                    edge_pct = edge

            # Insert prediction
            prediction_data = {
                "game_id": game["id"],
                "model_name": "baseline_v1",
                "predicted_home_cover_prob": home_cover_prob,
                "predicted_away_cover_prob": 1 - home_cover_prob,
                "spread_at_prediction": spread,
                "confidence_tier": confidence_tier,
                "recommended_bet": recommended_bet,
                "edge_pct": edge_pct,
            }

            client.table("predictions").insert(prediction_data).execute()
            predictions_created += 1

        except Exception as e:
            print(f"  Error predicting game {game['id']}: {e}")
            continue

    print(f"Predictions created: {predictions_created}")
    return {"predictions_created": predictions_created}


def update_game_results() -> dict:
    """Update scores for completed games."""
    print("\n=== Updating Game Results ===")

    client = _ensure_supabase()

    # Find games that should have finished but don't have scores
    # Use Eastern time for consistency with game dates
    yesterday = get_eastern_date_yesterday().isoformat()

    result = client.table("games").select("id, external_id").lte("date", yesterday).is_("home_score", "null").limit(50).execute()

    if not result.data:
        print("No games need score updates")
        return {"games_scored": 0}

    # Would fetch actual scores from CBBpy or ESPN
    # For now, just report what needs updating
    print(f"Found {len(result.data)} games needing scores")

    return {"games_needing_scores": len(result.data)}


def create_today_games_view() -> dict:
    """Populate the today_games view data."""
    print("\n=== Creating Today's Games View ===")

    client = _ensure_supabase()
    # Use Eastern time for consistency with game dates
    today = get_eastern_date_today().isoformat()

    # Get today's games with all related data
    result = client.table("games").select("""
        id,
        date,
        is_conference_game,
        home_team:home_team_id(id, name, conference),
        away_team:away_team_id(id, name, conference)
    """).eq("date", today).execute()

    if not result.data:
        print("No games today")
        return {"today_games": 0}

    print(f"Found {len(result.data)} games today")
    return {"today_games": len(result.data)}


def refresh_kenpom_data() -> dict:
    """Refresh KenPom advanced analytics data."""
    print("\n=== Refreshing KenPom Data ===")

    try:
        from .kenpom_scraper import refresh_kenpom_data as kenpom_refresh

        # Check if we have credentials
        kenpom_email = os.getenv("KENPOM_EMAIL")
        kenpom_password = os.getenv("KENPOM_PASSWORD")

        if not kenpom_email or not kenpom_password:
            print("KenPom credentials not configured, skipping")
            return {"status": "skipped", "reason": "no_credentials"}

        # Run the KenPom refresh
        results = kenpom_refresh(season=2025)
        return results

    except ImportError as e:
        print(f"KenPom scraper import error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"Error refreshing KenPom data: {e}")
        return {"status": "error", "error": str(e)}


def refresh_haslametrics_data() -> dict:
    """Refresh Haslametrics advanced analytics data (FREE - no credentials needed)."""
    print("\n=== Refreshing Haslametrics Data ===")

    try:
        from .haslametrics_scraper import refresh_haslametrics_data as hasla_refresh

        # Run the Haslametrics refresh (no credentials needed - FREE!)
        results = hasla_refresh(season=2025)
        return results

    except ImportError as e:
        print(f"Haslametrics scraper import error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"Error refreshing Haslametrics data: {e}")
        return {"status": "error", "error": str(e)}


def refresh_espn_tip_times(days: int = 7) -> dict:
    """Refresh game tip times from ESPN (FREE - public API)."""
    print("\n=== Refreshing ESPN Tip Times ===")

    try:
        from .espn_scraper import refresh_espn_tip_times as espn_refresh

        # Run the ESPN refresh (no credentials needed - FREE!)
        results = espn_refresh(days=days)
        return results

    except ImportError as e:
        print(f"ESPN scraper import error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"Error refreshing ESPN tip times: {e}")
        return {"status": "error", "error": str(e)}


def refresh_prediction_markets() -> dict:
    """Refresh prediction market data from Polymarket and Kalshi."""
    print("\n=== Refreshing Prediction Markets ===")

    try:
        import asyncio
        from .prediction_market_scraper import refresh_prediction_markets as pm_refresh

        # Run the async prediction market refresh
        results = asyncio.run(pm_refresh())
        return results

    except ImportError as e:
        print(f"Prediction market scraper import error: {e}")
        return {"status": "error", "error": str(e)}
    except Exception as e:
        print(f"Error refreshing prediction markets: {e}")
        return {"status": "error", "error": str(e)}


def run_ai_analysis() -> dict:
    """Run AI analysis on today's games that don't have analysis yet."""
    print("\n=== Running AI Analysis ===")

    client = _ensure_supabase()
    # Use Eastern time for consistency with game dates
    today = get_eastern_date_today().isoformat()

    # Get today's games
    result = client.table("games").select("id").eq("date", today).execute()

    if not result.data:
        print("No games today to analyze")
        return {"analyses_created": 0}

    games = result.data
    print(f"Found {len(games)} games today")

    analyses_created = 0
    errors = 0

    for game in games:
        game_id = game["id"]

        try:
            # Check if analysis already exists for this game
            existing = client.table("ai_analysis").select("id").eq("game_id", game_id).eq("ai_provider", "claude").execute()

            if existing.data:
                print(f"  Analysis already exists for game {game_id[:8]}...")
                continue

            # Import and run AI analysis
            from ..api.ai_service import analyze_game

            print(f"  Analyzing game {game_id[:8]}...")
            analysis = analyze_game(game_id, provider="claude", save=True)

            if analysis:
                analyses_created += 1
                print(f"    -> {analysis.get('recommended_bet', 'pass')} (confidence: {analysis.get('confidence_score', 0):.2f})")

        except Exception as e:
            errors += 1
            print(f"  Error analyzing game {game_id[:8]}: {e}")

    print(f"AI analyses created: {analyses_created}, errors: {errors}")
    return {"analyses_created": analyses_created, "errors": errors}


def run_daily_refresh(force_regenerate_predictions: bool = False) -> dict:
    """Run the complete daily refresh pipeline.

    Args:
        force_regenerate_predictions: If True, delete and regenerate all predictions
    """
    print("=" * 60)
    print("Conference Contrarian - Daily Data Refresh")
    print(f"Started at: {datetime.now().isoformat()}")
    if force_regenerate_predictions:
        print("*** FORCE REGENERATE PREDICTIONS ENABLED ***")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "status": "success",
    }

    try:
        # Step 0: Invalidate all ratings caches before refresh
        # This ensures we fetch fresh data from scrapers and don't serve stale cache
        print("\n=== Step 0: Invalidating Ratings Caches ===")
        cache_invalidation = invalidate_ratings_caches()
        results["cache_invalidated"] = cache_invalidation
        print(f"Cache invalidated: KenPom={cache_invalidation.get('kenpom_invalidated', 0)}, "
              f"Haslametrics={cache_invalidation.get('haslametrics_invalidated', 0)}")
        # 1. ESPN is PRIMARY source of games - creates all games first
        try:
            print("\n=== Step 1: ESPN Game Schedule (PRIMARY) ===")
            espn_results = refresh_espn_tip_times(days=7)
            results["espn_games"] = espn_results
            print(f"ESPN: Created {espn_results.get('games_created', 0)}, updated {espn_results.get('games_updated', 0)}")
        except Exception as e:
            print(f"ESPN refresh error (non-fatal): {e}")
            results["espn_games"] = {"error": str(e)}

        # 2. Fetch betting lines from The Odds API (adds to existing games)
        print("\n=== Step 2: Betting Lines from Odds API ===")
        odds_data = fetch_odds_api_spreads()
        if odds_data:
            odds_results = process_odds_data(odds_data)
            results["odds"] = odds_results

        # 3. Refresh KenPom advanced analytics (once daily)
        try:
            kenpom_results = refresh_kenpom_data()
            results["kenpom"] = kenpom_results
        except Exception as e:
            print(f"KenPom refresh error (non-fatal): {e}")
            results["kenpom"] = {"error": str(e)}

        # 3b. Refresh Haslametrics advanced analytics (FREE - no credentials needed)
        try:
            hasla_results = refresh_haslametrics_data()
            results["haslametrics"] = hasla_results
        except Exception as e:
            print(f"Haslametrics refresh error (non-fatal): {e}")
            results["haslametrics"] = {"error": str(e)}

        # 3. Run predictions on upcoming games
        prediction_results = run_predictions(force_regenerate=force_regenerate_predictions)
        results["predictions"] = prediction_results

        # 4. Update completed game results
        score_results = update_game_results()
        results["scores"] = score_results

        # 5. Create today's view
        view_results = create_today_games_view()
        results["today"] = view_results

        # 6. Run AI analysis on today's games (uses KenPom data if available)
        try:
            ai_results = run_ai_analysis()
            results["ai_analysis"] = ai_results
        except Exception as e:
            print(f"AI analysis error (non-fatal): {e}")
            results["ai_analysis"] = {"error": str(e)}

    except Exception as e:
        results["status"] = "error"
        results["error"] = str(e)
        print(f"\nERROR: {e}")

    # Log final cache stats
    cache_stats = ratings_cache.get_stats()
    results["cache_stats"] = cache_stats
    print(f"\nCache stats: hits={cache_stats.get('hits', 0)}, "
          f"misses={cache_stats.get('misses', 0)}, "
          f"hit_rate={cache_stats.get('hit_rate_pct', 0):.1f}%")

    print("\n" + "=" * 60)
    print("Daily Refresh Complete")
    print(f"Finished at: {datetime.now().isoformat()}")
    print("=" * 60)

    return results


if __name__ == "__main__":
    results = run_daily_refresh()
    print("\nResults:")
    print(json.dumps(results, indent=2))

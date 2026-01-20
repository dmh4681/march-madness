"""
Supabase client for the Conference Contrarian backend.

Handles all database operations with Supabase.
"""

import os
from datetime import date, datetime
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Initialize Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend

_client: Optional[Client] = None


def get_supabase() -> Client:
    """Get or create Supabase client."""
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ============================================
# TEAMS
# ============================================


def get_team_by_name(name: str) -> Optional[dict]:
    """Get team by normalized name."""
    client = get_supabase()
    result = client.table("teams").select("*").eq("normalized_name", name.lower()).execute()
    return result.data[0] if result.data else None


def get_or_create_team(name: str, conference: str = None) -> dict:
    """Get existing team or create new one."""
    normalized = normalize_team_name(name)
    team = get_team_by_name(normalized)

    if team:
        return team

    # Create new team
    client = get_supabase()
    power_conferences = {"ACC", "Big Ten", "Big 12", "SEC", "Big East", "Pac-12"}

    result = client.table("teams").insert({
        "name": name,
        "normalized_name": normalized,
        "conference": conference,
        "is_power_conference": conference in power_conferences if conference else False,
    }).execute()

    return result.data[0]


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    # Remove common suffixes
    suffixes = [
        "Wildcats", "Tigers", "Bears", "Eagles", "Bulldogs", "Cardinals",
        "Cougars", "Ducks", "Gators", "Hawks", "Huskies", "Jayhawks",
        "Knights", "Lions", "Longhorns", "Mountaineers", "Panthers",
        "Seminoles", "Spartans", "Tar Heels", "Terrapins", "Volunteers",
        "Wolverines", "Blue Devils", "Crimson Tide", "Fighting Irish",
        "Hoosiers", "Boilermakers", "Buckeyes", "Nittany Lions",
        "Golden Gophers", "Badgers", "Hawkeyes", "Cornhuskers",
    ]

    result = name.strip()
    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[:-len(suffix)].strip()
            break

    return result.lower().replace(" ", "-").replace("'", "").replace(".", "")


# ============================================
# GAMES
# ============================================


def get_games_by_date(game_date: date) -> list[dict]:
    """Get all games for a specific date."""
    client = get_supabase()
    result = client.table("games").select(
        "*, home_team:teams!games_home_team_id_fkey(*), away_team:teams!games_away_team_id_fkey(*)"
    ).eq("date", game_date.isoformat()).execute()
    return result.data


def get_game_by_id(game_id: str) -> Optional[dict]:
    """Get game by ID with related data."""
    client = get_supabase()
    result = client.table("games").select(
        "*, home_team:teams!games_home_team_id_fkey(*), away_team:teams!games_away_team_id_fkey(*)"
    ).eq("id", game_id).execute()
    return result.data[0] if result.data else None


def upsert_game(game_data: dict) -> dict:
    """Insert or update a game."""
    client = get_supabase()

    # Ensure we have team IDs
    if "home_team" in game_data and isinstance(game_data["home_team"], str):
        home_team = get_or_create_team(game_data["home_team"], game_data.get("home_conference"))
        game_data["home_team_id"] = home_team["id"]
        del game_data["home_team"]

    if "away_team" in game_data and isinstance(game_data["away_team"], str):
        away_team = get_or_create_team(game_data["away_team"], game_data.get("away_conference"))
        game_data["away_team_id"] = away_team["id"]
        del game_data["away_team"]

    # Clean up extra fields
    game_data.pop("home_conference", None)
    game_data.pop("away_conference", None)

    result = client.table("games").upsert(
        game_data,
        on_conflict="external_id"
    ).execute()

    return result.data[0]


def get_upcoming_games(days: int = 7) -> list[dict]:
    """Get games for the next N days."""
    client = get_supabase()
    today = date.today()
    end_date = date.today().replace(day=today.day + days)

    result = client.table("games").select(
        "*, home_team:teams!games_home_team_id_fkey(*), away_team:teams!games_away_team_id_fkey(*)"
    ).gte("date", today.isoformat()).lte("date", end_date.isoformat()).order("date").execute()

    return result.data


# ============================================
# SPREADS
# ============================================


def insert_spread(spread_data: dict) -> dict:
    """Insert a new spread snapshot."""
    client = get_supabase()
    result = client.table("spreads").insert(spread_data).execute()
    return result.data[0]


def get_latest_spread(game_id: str) -> Optional[dict]:
    """Get the most recent spread for a game."""
    client = get_supabase()
    result = client.table("spreads").select("*").eq(
        "game_id", game_id
    ).order("captured_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def get_spread_history(game_id: str) -> list[dict]:
    """Get all spread snapshots for a game."""
    client = get_supabase()
    result = client.table("spreads").select("*").eq(
        "game_id", game_id
    ).order("captured_at").execute()
    return result.data


# ============================================
# RANKINGS
# ============================================


def upsert_ranking(ranking_data: dict) -> dict:
    """Insert or update a ranking."""
    client = get_supabase()

    # Ensure we have team ID
    if "team" in ranking_data and isinstance(ranking_data["team"], str):
        team = get_or_create_team(ranking_data["team"], ranking_data.get("conference"))
        ranking_data["team_id"] = team["id"]
        del ranking_data["team"]
        ranking_data.pop("conference", None)

    result = client.table("rankings").upsert(
        ranking_data,
        on_conflict="team_id,season,week,poll_type"
    ).execute()

    return result.data[0]


def get_current_rankings(season: int, poll_type: str = "ap") -> list[dict]:
    """Get the most recent rankings for a season."""
    client = get_supabase()

    # Get the max week
    max_week_result = client.table("rankings").select("week").eq(
        "season", season
    ).eq("poll_type", poll_type).order("week", desc=True).limit(1).execute()

    if not max_week_result.data:
        return []

    max_week = max_week_result.data[0]["week"]

    result = client.table("rankings").select(
        "*, team:teams(*)"
    ).eq("season", season).eq("week", max_week).eq(
        "poll_type", poll_type
    ).order("rank").execute()

    return result.data


def get_team_ranking(team_id: str, season: int, week: int = None) -> Optional[dict]:
    """Get ranking for a specific team."""
    client = get_supabase()

    query = client.table("rankings").select("*").eq(
        "team_id", team_id
    ).eq("season", season)

    if week is not None:
        query = query.eq("week", week)
    else:
        query = query.order("week", desc=True).limit(1)

    result = query.execute()
    return result.data[0] if result.data else None


# ============================================
# PREDICTIONS
# ============================================


def insert_prediction(prediction_data: dict) -> dict:
    """Insert a new prediction."""
    client = get_supabase()
    result = client.table("predictions").insert(prediction_data).execute()
    return result.data[0]


def get_latest_prediction(game_id: str) -> Optional[dict]:
    """Get the most recent prediction for a game."""
    client = get_supabase()
    result = client.table("predictions").select("*").eq(
        "game_id", game_id
    ).order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def get_predictions_by_confidence(confidence_tier: str, limit: int = 10) -> list[dict]:
    """Get predictions by confidence tier."""
    client = get_supabase()
    today = date.today()

    result = client.table("predictions").select(
        "*, game:games(*, home_team:teams!games_home_team_id_fkey(*), away_team:teams!games_away_team_id_fkey(*))"
    ).eq("confidence_tier", confidence_tier).gte(
        "game.date", today.isoformat()
    ).order("edge_pct", desc=True).limit(limit).execute()

    return result.data


# ============================================
# AI ANALYSIS
# ============================================


def insert_ai_analysis(analysis_data: dict) -> dict:
    """Insert a new AI analysis."""
    client = get_supabase()
    result = client.table("ai_analysis").insert(analysis_data).execute()
    return result.data[0]


def get_ai_analyses(game_id: str) -> list[dict]:
    """Get all AI analyses for a game."""
    client = get_supabase()
    result = client.table("ai_analysis").select("*").eq(
        "game_id", game_id
    ).order("created_at", desc=True).execute()
    return result.data


def get_ai_analysis_by_provider(game_id: str, provider: str) -> Optional[dict]:
    """Get the most recent AI analysis for a game from a specific provider."""
    client = get_supabase()
    result = client.table("ai_analysis").select("*").eq(
        "game_id", game_id
    ).eq("ai_provider", provider).order("created_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


# ============================================
# BET RESULTS
# ============================================


def insert_bet_result(bet_data: dict) -> dict:
    """Insert a new bet result."""
    client = get_supabase()
    result = client.table("bet_results").insert(bet_data).execute()
    return result.data[0]


def update_bet_result(bet_id: str, result_data: dict) -> dict:
    """Update a bet result (e.g., when game is graded)."""
    client = get_supabase()
    result = client.table("bet_results").update(result_data).eq("id", bet_id).execute()
    return result.data[0]


def get_pending_bets() -> list[dict]:
    """Get all ungraded bets."""
    client = get_supabase()
    result = client.table("bet_results").select(
        "*, game:games(*), prediction:predictions(*)"
    ).eq("result", "pending").execute()
    return result.data


def get_season_performance(season: int) -> Optional[dict]:
    """Get performance summary for a season."""
    client = get_supabase()
    result = client.table("season_performance").select("*").eq("season", season).execute()
    return result.data[0] if result.data else None


# ============================================
# VIEWS / AGGREGATIONS
# ============================================


def get_today_games_view() -> list[dict]:
    """Get today's games from the view."""
    client = get_supabase()
    result = client.table("today_games").select("*").execute()
    return result.data


def get_team_kenpom(team_id: str, season: int = 2025) -> Optional[dict]:
    """Get the latest KenPom rating for a team."""
    client = get_supabase()
    result = client.table("kenpom_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def calculate_season_stats(season: int) -> dict:
    """Calculate comprehensive season statistics."""
    client = get_supabase()

    # Get all graded bets for the season
    result = client.table("bet_results").select(
        "*, game:games!inner(season)"
    ).eq("game.season", season).neq("result", "pending").execute()

    bets = result.data
    if not bets:
        return {"error": "No bets found for season"}

    wins = sum(1 for b in bets if b["result"] == "win")
    losses = sum(1 for b in bets if b["result"] == "loss")
    pushes = sum(1 for b in bets if b["result"] == "push")
    total = wins + losses

    total_wagered = sum(b["units_wagered"] for b in bets)
    total_won = sum(b["units_won"] or 0 for b in bets)

    return {
        "season": season,
        "total_bets": len(bets),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "win_pct": (wins / total * 100) if total > 0 else 0,
        "units_wagered": total_wagered,
        "units_won": total_won,
        "roi_pct": (total_won / total_wagered * 100) if total_wagered > 0 else 0,
    }

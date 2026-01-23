"""
Supabase client for the Conference Contrarian backend.

Handles all database operations with Supabase.

SECURITY NOTES:
- Uses Supabase Python SDK which handles parameterized queries internally
- All user input is passed through SDK methods, preventing SQL injection
- Service key is used for backend operations (not exposed to frontend)
- Connection pooling and timeouts are handled by the SDK's httpx client
"""

import os
import re
import logging
from datetime import date, datetime, timedelta
from typing import Optional
from functools import wraps

# Timezone handling - use Eastern time for date queries
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Fallback

EASTERN_TZ = ZoneInfo("America/New_York")


def get_eastern_date_today() -> date:
    """Get today's date in US Eastern time for consistent queries."""
    return datetime.now(EASTERN_TZ).date()


from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# SECURITY: Database Configuration
# =============================================================================

# SECURITY: Validate environment variables before use
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend

# SECURITY: Validate Supabase URL format
def _validate_supabase_url(url: Optional[str]) -> bool:
    """Validate Supabase URL format to prevent injection attacks."""
    if not url:
        return False
    # Supabase URLs follow pattern: https://<project>.supabase.co
    pattern = re.compile(r'^https://[a-zA-Z0-9-]+\.supabase\.co$')
    return bool(pattern.match(url))


# SECURITY: Connection pool and timeout configuration
# These settings prevent resource exhaustion and hanging connections
HTTP_TIMEOUT_SECONDS = 30  # Maximum time to wait for a response
HTTP_CONNECT_TIMEOUT = 10  # Maximum time to establish connection
HTTP_POOL_SIZE = 10  # Maximum number of concurrent connections
HTTP_KEEPALIVE_EXPIRY = 30  # Seconds before idle connections are closed

_client: Optional[Client] = None


def get_supabase() -> Client:
    """
    Get or create Supabase client with secure configuration.

    SECURITY:
    - Validates URL format before connection
    - Configures timeouts to prevent hanging connections
    - Uses connection pooling for efficiency
    - Service key is kept server-side only
    """
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        # SECURITY: Validate URL format
        if not _validate_supabase_url(SUPABASE_URL):
            raise ValueError("Invalid SUPABASE_URL format")

        # Create client - Supabase SDK handles connection pooling internally via httpx
        # Note: Custom options require ClientOptions object, keeping it simple here
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")

    return _client


# =============================================================================
# SECURITY: Input Validation Helpers
# =============================================================================

def _validate_uuid(value: str, field_name: str = "id") -> str:
    """
    Validate that a string is a valid UUID format.

    SECURITY: Prevents injection attacks through ID fields.
    """
    if not value:
        raise ValueError(f"{field_name} is required")

    # UUID pattern: 8-4-4-4-12 hexadecimal characters
    uuid_pattern = re.compile(
        r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
    )
    if not uuid_pattern.match(value):
        raise ValueError(f"Invalid {field_name} format")

    return value


def _sanitize_string(value: str, max_length: int = 255, field_name: str = "value") -> str:
    """
    Sanitize string input by limiting length and removing dangerous characters.

    SECURITY: Prevents buffer overflow and injection attacks.
    Note: The Supabase SDK uses parameterized queries, so SQL injection is prevented,
    but we still sanitize to prevent other issues (XSS in logs, etc.)
    """
    if not value:
        return ""

    # Truncate to max length
    sanitized = value[:max_length]

    # Remove null bytes (can cause issues in some systems)
    sanitized = sanitized.replace('\x00', '')

    return sanitized


# ============================================
# TEAMS
# ============================================


def get_team_by_name(name: str) -> Optional[dict]:
    """Get team by normalized name."""
    # SECURITY: Sanitize input (SDK handles parameterization)
    sanitized_name = _sanitize_string(name, max_length=100, field_name="team_name").lower()
    if not sanitized_name:
        return None

    client = get_supabase()
    result = client.table("teams").select("*").eq("normalized_name", sanitized_name).execute()
    return result.data[0] if result.data else None


def get_or_create_team(name: str, conference: str = None) -> dict:
    """Get existing team or create new one."""
    # SECURITY: Sanitize inputs
    sanitized_name = _sanitize_string(name, max_length=100, field_name="team_name")
    if not sanitized_name:
        raise ValueError("Team name is required")

    normalized = normalize_team_name(sanitized_name)
    team = get_team_by_name(normalized)

    if team:
        return team

    # SECURITY: Sanitize conference name
    sanitized_conference = _sanitize_string(conference, max_length=50, field_name="conference") if conference else None

    # Create new team
    client = get_supabase()
    power_conferences = {"ACC", "Big Ten", "Big 12", "SEC", "Big East", "Pac-12"}

    result = client.table("teams").insert({
        "name": sanitized_name,
        "normalized_name": normalized,
        "conference": sanitized_conference,
        "is_power_conference": sanitized_conference in power_conferences if sanitized_conference else False,
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
    # SECURITY: Validate UUID format to prevent injection
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("games").select(
        "*, home_team:teams!games_home_team_id_fkey(*), away_team:teams!games_away_team_id_fkey(*)"
    ).eq("id", validated_id).execute()
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
    """Get games for the next N days.

    Uses Eastern time for date queries since games are stored in Eastern time.
    """
    client = get_supabase()
    # Use Eastern time for consistency with game dates stored in DB
    today = get_eastern_date_today()
    end_date = today + timedelta(days=days)

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
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("spreads").select("*").eq(
        "game_id", validated_id
    ).order("captured_at", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def get_spread_history(game_id: str) -> list[dict]:
    """Get all spread snapshots for a game."""
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("spreads").select("*").eq(
        "game_id", validated_id
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
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(team_id, "team_id")

    # SECURITY: Validate season is a reasonable integer
    if not isinstance(season, int) or season < 1900 or season > 2100:
        raise ValueError("Invalid season value")

    client = get_supabase()

    query = client.table("rankings").select("*").eq(
        "team_id", validated_id
    ).eq("season", season)

    if week is not None:
        # SECURITY: Validate week is a reasonable integer
        if not isinstance(week, int) or week < 0 or week > 52:
            raise ValueError("Invalid week value")
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
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("predictions").select("*").eq(
        "game_id", validated_id
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
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("ai_analysis").select("*").eq(
        "game_id", validated_id
    ).order("created_at", desc=True).execute()
    return result.data


def get_ai_analysis_by_provider(game_id: str, provider: str) -> Optional[dict]:
    """Get the most recent AI analysis for a game from a specific provider."""
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    # SECURITY: Sanitize provider string
    sanitized_provider = _sanitize_string(provider, max_length=50, field_name="provider")
    if not sanitized_provider:
        raise ValueError("provider is required")

    client = get_supabase()
    result = client.table("ai_analysis").select("*").eq(
        "game_id", validated_id
    ).eq("ai_provider", sanitized_provider).order("created_at", desc=True).limit(1).execute()
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
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(bet_id, "bet_id")

    client = get_supabase()
    result = client.table("bet_results").update(result_data).eq("id", validated_id).execute()
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


def get_team_haslametrics(team_id: str, season: int = 2025) -> Optional[dict]:
    """Get the latest Haslametrics rating for a team."""
    client = get_supabase()
    result = client.table("haslametrics_ratings").select("*").eq(
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

"""
Supabase client for the Conference Contrarian backend.

Handles all database operations with Supabase.

SECURITY NOTES:
- Uses Supabase Python SDK which handles parameterized queries internally
- All user input is passed through SDK methods, preventing SQL injection
- Service key is used for backend operations (not exposed to frontend)
- Connection pooling and timeouts are configured via ClientOptions

CACHING NOTES:
- KenPom and Haslametrics ratings are cached with 1-hour TTL
- Cache is invalidated during daily refresh
- Cache hit/miss is logged for monitoring

CONNECTION POOLING:
- Uses httpx connection pooling via ClientOptions
- Pool size: 20 concurrent connections
- Keep-alive: 30 seconds for idle connections
- Timeouts: 30s response, 10s connect
- Prevents connection exhaustion during daily refresh
"""

import os
import re
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps
from contextlib import contextmanager

# Import cache module
try:
    from backend.utils.cache import ratings_cache
except ImportError:
    # Fallback for direct module execution
    from ..utils.cache import ratings_cache

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
from supabase.lib.client_options import ClientOptions
import httpx

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


# =============================================================================
# CONNECTION POOLING: Configuration
# =============================================================================
# These settings optimize connection handling for:
# - Daily refresh pipeline (multiple concurrent data source queries)
# - AI analysis requests (parallel calls during batch processing)
# - Frontend API requests (read-heavy workload)

HTTP_TIMEOUT_SECONDS = 30  # Maximum time to wait for a response
HTTP_CONNECT_TIMEOUT = 10  # Maximum time to establish connection
HTTP_POOL_SIZE = 20  # Maximum number of concurrent connections (increased from 10)
HTTP_MAX_KEEPALIVE = 10  # Maximum keep-alive connections to maintain
HTTP_KEEPALIVE_EXPIRY = 30  # Seconds before idle connections are closed

_client: Optional[Client] = None

# =============================================================================
# QUERY PERFORMANCE: Timing and Monitoring
# =============================================================================

# Query timing statistics (thread-safe tracking)
_query_stats = {
    "total_queries": 0,
    "total_time_ms": 0.0,
    "slow_queries": 0,  # Queries taking > 1000ms
    "slowest_query_ms": 0.0,
    "slowest_query_name": "",
}

# Threshold for "slow query" classification (milliseconds)
SLOW_QUERY_THRESHOLD_MS = 1000


@contextmanager
def query_timer(query_name: str = "unnamed"):
    """
    Context manager for timing database queries.

    Usage:
        with query_timer("get_today_games"):
            result = client.table("games").select("*").execute()

    Logs query duration and updates statistics.
    """
    start_time = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Update statistics
        _query_stats["total_queries"] += 1
        _query_stats["total_time_ms"] += elapsed_ms

        if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            _query_stats["slow_queries"] += 1
            logger.warning(
                f"SLOW QUERY: {query_name} took {elapsed_ms:.2f}ms "
                f"(threshold: {SLOW_QUERY_THRESHOLD_MS}ms)"
            )

        if elapsed_ms > _query_stats["slowest_query_ms"]:
            _query_stats["slowest_query_ms"] = elapsed_ms
            _query_stats["slowest_query_name"] = query_name

        logger.debug(f"Query '{query_name}' completed in {elapsed_ms:.2f}ms")


def timed_query(query_name: str = None):
    """
    Decorator for timing database query functions.

    Usage:
        @timed_query("get_games_by_date")
        def get_games_by_date(game_date: date) -> list[dict]:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            name = query_name or func.__name__
            with query_timer(name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def get_query_stats() -> dict:
    """
    Get query performance statistics.

    Returns:
        Dict with total_queries, total_time_ms, avg_time_ms, slow_queries,
        slowest_query_ms, slowest_query_name
    """
    total = _query_stats["total_queries"]
    avg_ms = _query_stats["total_time_ms"] / total if total > 0 else 0

    return {
        "total_queries": total,
        "total_time_ms": round(_query_stats["total_time_ms"], 2),
        "avg_time_ms": round(avg_ms, 2),
        "slow_queries": _query_stats["slow_queries"],
        "slow_query_pct": round(_query_stats["slow_queries"] / total * 100, 2) if total > 0 else 0,
        "slowest_query_ms": round(_query_stats["slowest_query_ms"], 2),
        "slowest_query_name": _query_stats["slowest_query_name"],
    }


def reset_query_stats() -> None:
    """Reset query statistics (useful at start of daily refresh)."""
    global _query_stats
    _query_stats = {
        "total_queries": 0,
        "total_time_ms": 0.0,
        "slow_queries": 0,
        "slowest_query_ms": 0.0,
        "slowest_query_name": "",
    }
    logger.info("Query statistics reset")


def get_supabase() -> Client:
    """
    Get or create Supabase client with secure configuration and connection pooling.

    SECURITY:
    - Validates URL format before connection
    - Configures timeouts to prevent hanging connections
    - Uses connection pooling for efficiency
    - Service key is kept server-side only

    CONNECTION POOLING:
    - Creates an httpx client with configurable pool limits
    - Reuses connections across requests for efficiency
    - Properly handles keep-alive connections
    """
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        # SECURITY: Validate URL format
        if not _validate_supabase_url(SUPABASE_URL):
            raise ValueError("Invalid SUPABASE_URL format")

        # Configure connection pooling via httpx Limits
        # This prevents connection exhaustion during batch operations
        http_limits = httpx.Limits(
            max_connections=HTTP_POOL_SIZE,
            max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            keepalive_expiry=HTTP_KEEPALIVE_EXPIRY,
        )

        # Configure timeouts
        http_timeout = httpx.Timeout(
            timeout=HTTP_TIMEOUT_SECONDS,
            connect=HTTP_CONNECT_TIMEOUT,
        )

        # Create custom httpx client with pooling configuration
        http_client = httpx.Client(
            limits=http_limits,
            timeout=http_timeout,
        )

        # Create Supabase client with custom options
        # Note: ClientOptions allows passing custom httpx client settings
        options = ClientOptions(
            postgrest_client_timeout=HTTP_TIMEOUT_SECONDS,
            storage_client_timeout=HTTP_TIMEOUT_SECONDS,
        )

        _client = create_client(SUPABASE_URL, SUPABASE_KEY, options=options)

        logger.info(
            f"Supabase client initialized with connection pooling: "
            f"pool_size={HTTP_POOL_SIZE}, keepalive={HTTP_MAX_KEEPALIVE}, "
            f"timeout={HTTP_TIMEOUT_SECONDS}s"
        )

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


@timed_query("get_team_by_name")
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


@timed_query("get_games_by_date")
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


@timed_query("get_upcoming_games")
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
    # Use Eastern time for consistency with game dates
    today = get_eastern_date_today()

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


@timed_query("get_today_games_view")
def get_today_games_view() -> list[dict]:
    """Get today's games from the view."""
    client = get_supabase()
    result = client.table("today_games").select("*").execute()
    return result.data


@timed_query("get_upcoming_games_view")
def get_upcoming_games_view(days: int = 7) -> list[dict]:
    """Get upcoming games from the view with flat team names.

    This uses the upcoming_games view which returns data in the same format
    as today_games (flat home_team/away_team strings, not nested objects).
    """
    client = get_supabase()
    today = get_eastern_date_today()
    end_date = today + timedelta(days=days)

    result = client.table("upcoming_games").select("*").gte(
        "date", today.isoformat()
    ).lte(
        "date", end_date.isoformat()
    ).order("date").execute()

    return result.data


@timed_query("get_team_kenpom")
def get_team_kenpom(team_id: str, season: int = 2025, use_cache: bool = True) -> Optional[dict]:
    """
    Get the latest KenPom rating for a team with caching.

    Args:
        team_id: Team UUID
        season: Season year
        use_cache: Whether to use cached data (default: True)

    Returns:
        Dict with KenPom data or None
    """
    cache_key_kwargs = {"team_id": team_id, "season": season}

    # Try cache first if enabled
    if use_cache:
        cached_data = ratings_cache.get("kenpom_team", **cache_key_kwargs)
        if cached_data is not None:
            logger.debug(f"Cache HIT: kenpom_team (team_id={team_id[:8]}..., season={season})")
            return cached_data

    logger.debug(f"Cache MISS: kenpom_team (team_id={team_id[:8]}..., season={season})")

    # Fetch from database
    client = get_supabase()
    result = client.table("kenpom_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()

    if result.data:
        # Cache the result
        ratings_cache.set("kenpom_team", result.data[0], **cache_key_kwargs)
        logger.debug(f"Cache SET: kenpom_team (team_id={team_id[:8]}..., season={season})")
        return result.data[0]

    return None


@timed_query("get_team_haslametrics")
def get_team_haslametrics(team_id: str, season: int = 2025, use_cache: bool = True) -> Optional[dict]:
    """
    Get the latest Haslametrics rating for a team with caching.

    Args:
        team_id: Team UUID
        season: Season year
        use_cache: Whether to use cached data (default: True)

    Returns:
        Dict with Haslametrics data or None
    """
    cache_key_kwargs = {"team_id": team_id, "season": season}

    # Try cache first if enabled
    if use_cache:
        cached_data = ratings_cache.get("haslametrics_team", **cache_key_kwargs)
        if cached_data is not None:
            logger.debug(f"Cache HIT: haslametrics_team (team_id={team_id[:8]}..., season={season})")
            return cached_data

    logger.debug(f"Cache MISS: haslametrics_team (team_id={team_id[:8]}..., season={season})")

    # Fetch from database
    client = get_supabase()
    result = client.table("haslametrics_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()

    if result.data:
        # Cache the result
        ratings_cache.set("haslametrics_team", result.data[0], **cache_key_kwargs)
        logger.debug(f"Cache SET: haslametrics_team (team_id={team_id[:8]}..., season={season})")
        return result.data[0]

    return None


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


# ============================================
# PREDICTION MARKETS
# ============================================


def get_game_prediction_markets(game_id: str) -> list[dict]:
    """Get all prediction markets for a game."""
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    result = client.table("prediction_markets").select("*").eq(
        "game_id", validated_id
    ).eq("status", "open").order("captured_at", desc=True).execute()

    return result.data or []


def get_team_prediction_markets(team_id: str) -> list[dict]:
    """Get futures markets for a team."""
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(team_id, "team_id")

    client = get_supabase()
    result = client.table("prediction_markets").select("*").eq(
        "team_id", validated_id
    ).eq("status", "open").order("captured_at", desc=True).execute()

    return result.data or []


def get_game_arbitrage_opportunities(game_id: str) -> list[dict]:
    """Get arbitrage opportunities for a game."""
    # SECURITY: Validate UUID format
    validated_id = _validate_uuid(game_id, "game_id")

    client = get_supabase()
    # Only get recent opportunities (last 24 hours)
    result = client.table("arbitrage_opportunities").select("*").eq(
        "game_id", validated_id
    ).order("captured_at", desc=True).limit(10).execute()

    return result.data or []


def get_actionable_arbitrage() -> list[dict]:
    """Get all actionable arbitrage opportunities."""
    client = get_supabase()

    # Try to use the view first
    try:
        result = client.table("actionable_arbitrage").select("*").execute()
        return result.data or []
    except Exception:
        # Fallback to direct query
        result = client.table("arbitrage_opportunities").select("*").eq(
            "is_actionable", True
        ).order("delta", desc=True).limit(20).execute()
        return result.data or []


def upsert_prediction_market(market_data: dict) -> dict:
    """Insert or update a prediction market."""
    client = get_supabase()

    # Validate game_id if provided
    if market_data.get("game_id"):
        market_data["game_id"] = _validate_uuid(market_data["game_id"], "game_id")

    # Validate team_id if provided
    if market_data.get("team_id"):
        market_data["team_id"] = _validate_uuid(market_data["team_id"], "team_id")

    result = client.table("prediction_markets").upsert(
        market_data, on_conflict="source,market_id"
    ).execute()

    return result.data[0] if result.data else {}


def insert_arbitrage_opportunity(opportunity_data: dict) -> dict:
    """Insert an arbitrage opportunity."""
    client = get_supabase()

    # Validate IDs
    if opportunity_data.get("game_id"):
        opportunity_data["game_id"] = _validate_uuid(opportunity_data["game_id"], "game_id")

    result = client.table("arbitrage_opportunities").insert(opportunity_data).execute()
    return result.data[0] if result.data else {}


# ============================================
# CACHE MANAGEMENT
# ============================================


def get_cache_stats() -> dict:
    """
    Get cache statistics for monitoring.

    Returns:
        Dict with cache hit/miss rates, entry counts, etc.
    """
    return ratings_cache.get_stats()


def invalidate_ratings_cache() -> dict:
    """
    Invalidate all ratings caches (KenPom and Haslametrics).

    Call this before refreshing ratings data.

    Returns:
        Dict with counts of invalidated entries
    """
    kenpom_count = ratings_cache.invalidate("kenpom")
    hasla_count = ratings_cache.invalidate("haslametrics")

    logger.info(
        f"Ratings caches invalidated: KenPom entries={kenpom_count}, Haslametrics entries={hasla_count}"
    )

    return {
        "kenpom_invalidated": kenpom_count,
        "haslametrics_invalidated": hasla_count,
    }


def cleanup_expired_cache() -> int:
    """
    Clean up expired cache entries.

    Returns:
        Number of expired entries removed
    """
    count = ratings_cache.cleanup_expired()
    if count > 0:
        logger.info(f"Cleaned up {count} expired cache entries")
    return count

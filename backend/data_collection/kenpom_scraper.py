"""
KenPom Data Scraper

Fetches advanced analytics from KenPom using kenpompy library.
Requires a paid KenPom subscription ($20/year).

KenPom Metrics Overview:
========================
KenPom (kenpom.com) is the gold standard for college basketball analytics.
Created by Ken Pomeroy, it uses tempo-free statistics to evaluate teams.

Key Metrics Collected:
- AdjO (Adjusted Offensive Efficiency): Points scored per 100 possessions,
  adjusted for opponent strength. Higher is better. Elite teams: 115+
- AdjD (Adjusted Defensive Efficiency): Points allowed per 100 possessions,
  adjusted for opponent strength. Lower is better. Elite teams: <95
- AdjEM (Adjusted Efficiency Margin): AdjO - AdjD. The core power rating.
  Top 25 teams typically have AdjEM > 15
- AdjT (Adjusted Tempo): Possessions per 40 minutes, adjusted for opponent.
  Shows pace preference. Slow (<65) vs Fast (>70)
- Luck: Deviation from expected record based on efficiency margin.
  Positive = winning more close games than expected (may regress)
- SOS (Strength of Schedule): Schedule difficulty based on opponent efficiency

How These Are Used in AI Analysis:
==================================
1. AdjEM differential predicts point spread (1 point per 1 AdjEM difference)
2. Tempo matchups affect totals (fast vs fast = higher scoring)
3. High luck values suggest regression (team may underperform expectations)
4. SOS context: A 15-5 team with hard schedule > 18-2 team with weak schedule

Usage:
    python -m backend.data_collection.kenpom_scraper
    python -m backend.data_collection.kenpom_scraper 2025  # Specific season

Environment variables:
    KENPOM_EMAIL - Your KenPom account email
    KENPOM_PASSWORD - Your KenPom account password
"""

import logging
import os
import sys
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Import cache after defining logger
try:
    from backend.utils.cache import ratings_cache, cached
except ImportError:
    # Fallback if running as standalone script
    from ..utils.cache import ratings_cache, cached

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
KENPOM_EMAIL = os.getenv("KENPOM_EMAIL")
KENPOM_PASSWORD = os.getenv("KENPOM_PASSWORD")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_team_name(name: str) -> str:
    """
    Normalize KenPom team name for matching with our database.

    KenPom uses specific naming conventions that differ from ESPN, The Odds API,
    and other sources. This function maps KenPom names to our normalized format.

    Normalization Process:
    1. Check explicit name_map for known differences
    2. Apply basic normalization: lowercase, remove punctuation, replace spaces

    Common KenPom Naming Differences:
    - Uses "Miami FL" instead of "Miami"
    - Uses full names like "Connecticut" not "UConn"
    - Inconsistent "St." vs "Saint" usage

    Args:
        name: Team name as it appears on KenPom

    Returns:
        Normalized team name matching our teams.normalized_name column

    Example:
        >>> normalize_team_name("North Carolina")
        'north-carolina'
        >>> normalize_team_name("UConn")
        'connecticut'
    """
    if not name:
        return ""

    # Explicit mappings for KenPom-specific naming conventions
    # Keys: KenPom names, Values: Our normalized_name format
    name_map = {
        "North Carolina": "north-carolina",
        "NC State": "nc-state",
        "Miami FL": "miami",
        "Miami OH": "miami-oh",
        "UConn": "connecticut",
        "Connecticut": "connecticut",
        "St. John's": "st-johns",
        "Saint John's": "st-johns",
        "Saint Mary's": "saint-marys",
        "St. Mary's": "saint-marys",
        "Ole Miss": "mississippi",
        "Mississippi": "mississippi",
        "USC": "southern-california",
        "Southern California": "southern-california",
        "UCF": "central-florida",
        "Central Florida": "central-florida",
        "UNLV": "unlv",
        "Nevada Las Vegas": "unlv",
        "BYU": "brigham-young",
        "Brigham Young": "brigham-young",
        "LSU": "louisiana-state",
        "Louisiana St.": "louisiana-state",
        "VCU": "virginia-commonwealth",
        "Virginia Commonwealth": "virginia-commonwealth",
        "SMU": "southern-methodist",
        "Southern Methodist": "southern-methodist",
        "TCU": "texas-christian",
        "Texas Christian": "texas-christian",
        "UTEP": "texas-el-paso",
        "Texas El Paso": "texas-el-paso",
        "UMass": "massachusetts",
        "Massachusetts": "massachusetts",
        "UNC Wilmington": "unc-wilmington",
        "UNC Greensboro": "unc-greensboro",
        "UNC Asheville": "unc-asheville",
    }

    # Check direct mapping first
    if name in name_map:
        return name_map[name]

    # Basic normalization
    result = name.lower()
    result = result.replace("'", "")
    result = result.replace(".", "")
    result = result.replace(" ", "-")
    result = result.replace("state", "-state").replace("--", "-")

    return result.strip("-")


def get_team_id(team_name: str) -> str | None:
    """
    Get team UUID from our database by matching normalized name.

    Implements a multi-stage matching strategy to handle naming variations:

    Matching Strategy (in order):
    1. Exact match on normalized_name
    2. Partial match (ILIKE %name%) - handles prefixes/suffixes
    3. Without "-state" suffix - handles "Ohio" vs "Ohio State" ambiguity

    This fuzzy matching is necessary because:
    - KenPom names don't always match our ESPN-sourced team names
    - Some teams have multiple common names (e.g., "Ole Miss" vs "Mississippi")
    - State schools are inconsistently named across sources

    Args:
        team_name: Team name from KenPom

    Returns:
        Team UUID if matched, None if no match found

    Note: Unmatched teams are logged and counted. If too many teams fail to match,
    check the name_map in normalize_team_name() and add missing mappings.
    """
    normalized = normalize_team_name(team_name)
    if not normalized:
        return None

    # Strategy 1: Exact match on normalized_name column
    # This is the most reliable - uses our explicit normalization
    result = supabase.table("teams").select("id").eq("normalized_name", normalized).execute()
    if result.data:
        return result.data[0]["id"]

    # Strategy 2: Partial match using ILIKE (case-insensitive)
    # Catches cases where normalization differs slightly
    result = supabase.table("teams").select("id, normalized_name").ilike(
        "normalized_name", f"%{normalized}%"
    ).execute()
    if result.data:
        return result.data[0]["id"]

    # Strategy 3: Try without "-state" suffix
    # Handles ambiguous cases like searching "ohio" matching "ohio-state"
    if "-state" in normalized:
        base_name = normalized.replace("-state", "")
        result = supabase.table("teams").select("id").ilike(
            "normalized_name", f"%{base_name}%"
        ).execute()
        if result.data:
            return result.data[0]["id"]

    return None


def _fetch_kenpom_ratings_uncached(season: int = 2025) -> pd.DataFrame | None:
    """
    Internal function to fetch KenPom ratings without caching.

    Technical Implementation:
    ========================
    Uses the kenpompy library which automates browser login to kenpom.com.
    KenPom doesn't have a public API, so we must scrape the website.

    The kenpompy library uses Selenium WebDriver to:
    1. Open a browser (Chrome/Chromium)
    2. Navigate to kenpom.com login page
    3. Enter credentials and authenticate
    4. Navigate to the ratings page
    5. Scrape the HTML table into a pandas DataFrame
    6. Close the browser

    get_pomeroy_ratings() specifically scrapes the main efficiency ratings table,
    which contains the core metrics (AdjEM, AdjO, AdjD, AdjT, Luck, SOS).

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)

    Returns:
        DataFrame with columns like:
        - Rk: Overall KenPom ranking
        - Team: Team name
        - Conf: Conference
        - W-L: Win-Loss record
        - AdjEM: Adjusted Efficiency Margin (main power rating)
        - AdjO, AdjO Rank: Adjusted Offense
        - AdjD, AdjD Rank: Adjusted Defense
        - AdjT, AdjT Rank: Adjusted Tempo
        - Luck, Luck Rank: Luck factor
        - SOS AdjEM, SOS AdjEM Rank: Strength of Schedule

    Note: Column names may vary between kenpompy versions. The store_kenpom_ratings()
    function handles multiple possible column name formats.

    Railway Deployment Note:
    =======================
    This function requires Chrome/Chromium installed. On Railway, you may need to:
    1. Use a Chrome buildpack, OR
    2. Run KenPom refresh locally and let other scrapers run on Railway
    """
    if not KENPOM_EMAIL or not KENPOM_PASSWORD:
        print("ERROR: KENPOM_EMAIL and KENPOM_PASSWORD must be set")
        return None

    try:
        from kenpompy.utils import login
        import kenpompy.misc as kp

        print(f"Logging into KenPom as {KENPOM_EMAIL}...")
        # login() opens a Selenium-controlled browser and authenticates
        # Returns a browser object that we pass to subsequent kenpompy functions
        browser = login(KENPOM_EMAIL, KENPOM_PASSWORD)

        print(f"Fetching Pomeroy ratings for {season}...")
        # get_pomeroy_ratings scrapes the main ratings table at kenpom.com
        # This is the "efficiency ratings" page, not the detailed team pages
        ratings = kp.get_pomeroy_ratings(browser, season=str(season))

        print(f"Fetched {len(ratings)} team ratings")
        print(f"Columns available: {list(ratings.columns)}")
        if len(ratings) > 0:
            print(f"Sample row: {ratings.iloc[0].to_dict()}")

        # Always close the browser to free resources
        browser.close()

        return ratings

    except ImportError as e:
        print(f"Import error - make sure kenpompy and selenium are installed: {e}")
        return None
    except Exception as e:
        print(f"Error fetching KenPom data: {e}")
        return None


def fetch_kenpom_ratings(season: int = 2025, use_cache: bool = True) -> pd.DataFrame | None:
    """
    Fetch KenPom Pomeroy ratings for a season with caching.

    Caches results for 1 hour to reduce API calls and login frequency.

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)
        use_cache: Whether to use cached data (default: True)

    Returns:
        DataFrame with KenPom ratings or None if failed
    """
    cache_key_kwargs = {"season": season}

    # Try cache first if enabled
    if use_cache:
        cached_data = ratings_cache.get("kenpom_ratings", **cache_key_kwargs)
        if cached_data is not None:
            logger.info(f"Cache HIT: kenpom_ratings (season={season})")
            print(f"Using cached KenPom ratings for {season}")
            return cached_data

    logger.info(f"Cache MISS: kenpom_ratings (season={season})")

    # Fetch fresh data
    ratings = _fetch_kenpom_ratings_uncached(season)

    # Cache the result if successful
    if ratings is not None and len(ratings) > 0:
        ratings_cache.set("kenpom_ratings", ratings, **cache_key_kwargs)
        logger.info(f"Cache SET: kenpom_ratings (season={season}, {len(ratings)} teams)")

    return ratings


def fetch_kenpom_fourfactors(season: int = 2025) -> pd.DataFrame | None:
    """Fetch Four Factors data from KenPom."""
    if not KENPOM_EMAIL or not KENPOM_PASSWORD:
        return None

    try:
        from kenpompy.utils import login
        import kenpompy.summary as kp

        browser = login(KENPOM_EMAIL, KENPOM_PASSWORD)
        fourfactors = kp.get_fourfactors(browser, season=str(season))
        browser.close()

        return fourfactors

    except Exception as e:
        print(f"Error fetching Four Factors: {e}")
        return None


def store_kenpom_ratings(df: pd.DataFrame, season: int) -> dict:
    """
    Store KenPom ratings in Supabase database.

    Data Transformation Process:
    ===========================
    1. Match each KenPom team name to our teams table
    2. Parse the various column formats (kenpompy versions differ)
    3. Extract and convert numeric values safely
    4. Insert into kenpom_ratings table

    Column Name Handling:
    ====================
    kenpompy's output column names have changed across versions.
    The get_col() helper tries multiple possible names for each metric:
    - "AdjO" vs "AdjO." vs "AdjOE"
    - "AdjO Rank" vs "AdjO.1" vs "AdjO Rk"

    This flexibility ensures we can handle kenpompy updates without code changes.

    Database Schema (kenpom_ratings table):
    ======================================
    - team_id: FK to teams.id
    - season: Year (e.g., 2025)
    - captured_date: Date when data was fetched
    - rank: Overall KenPom ranking (1-362)
    - adj_efficiency_margin: AdjO - AdjD (core power rating)
    - adj_offense/adj_offense_rank: Offensive efficiency
    - adj_defense/adj_defense_rank: Defensive efficiency (lower is better)
    - adj_tempo/adj_tempo_rank: Pace of play
    - luck/luck_rank: Performance vs expectation
    - sos_adj_em: Strength of schedule
    - wins/losses: Season record

    Args:
        df: DataFrame from kenpompy's get_pomeroy_ratings()
        season: Season year

    Returns:
        Dict with counts: {inserted, skipped, errors}
    """
    print(f"\n=== Storing KenPom Ratings ===")

    # Debug: Print actual column names from kenpompy
    # This helps diagnose issues when kenpompy updates change column names
    print(f"DataFrame columns: {list(df.columns)}")
    if len(df) > 0:
        print(f"Sample row: {df.iloc[0].to_dict()}")

    inserted = 0
    skipped = 0
    errors = 0

    for _, row in df.iterrows():
        try:
            team_name = row.get("Team", "")
            team_id = get_team_id(team_name)

            if not team_id:
                skipped += 1
                # Only log first 5 unmatched teams to avoid log spam
                if skipped <= 5:
                    print(f"  Could not match team: {team_name}")
                continue

            # Column name helper: tries multiple possible names for robustness
            # kenpompy versions use different column naming conventions
            def get_col(row, *names):
                """Try multiple column names and return first match."""
                for name in names:
                    val = row.get(name)
                    if val is not None and str(val) != 'nan':
                        return val
                return None

            # Parse W-L record (format: "15-5" or similar)
            wl = str(get_col(row, "W-L", "W-L.1", "Record") or "0-0")
            wins = safe_int(wl.split("-")[0]) if "-" in wl else 0
            losses = safe_int(wl.split("-")[-1]) if "-" in wl else 0

            # Build rating data dict with all possible column name variations
            # Each get_col call tries multiple column names in priority order
            rating_data = {
                "team_id": team_id,
                "season": season,
                "captured_date": datetime.now().date().isoformat(),
                # Core ranking
                "rank": safe_int(get_col(row, "Rk", "Rank", "Rk.")),
                # Efficiency Margin = AdjO - AdjD (main power rating)
                "adj_efficiency_margin": safe_float(get_col(row, "AdjEM", "AdjEM.", "NetRtg")),
                # Adjusted Offense: points per 100 possessions, adjusted for opponent
                "adj_offense": safe_float(get_col(row, "AdjO", "AdjO.", "AdjOE")),
                "adj_offense_rank": safe_int(get_col(row, "AdjO Rank", "AdjO.1", "AdjO Rk")),
                # Adjusted Defense: points allowed per 100 possessions (lower = better)
                "adj_defense": safe_float(get_col(row, "AdjD", "AdjD.", "AdjDE")),
                "adj_defense_rank": safe_int(get_col(row, "AdjD Rank", "AdjD.1", "AdjD Rk")),
                # Adjusted Tempo: possessions per 40 minutes
                "adj_tempo": safe_float(get_col(row, "AdjT", "AdjT.", "AdjTempo")),
                "adj_tempo_rank": safe_int(get_col(row, "AdjT Rank", "AdjT.1", "AdjT Rk")),
                # Luck: deviation from expected record (high = due for regression)
                "luck": safe_float(get_col(row, "Luck", "Luck.")),
                "luck_rank": safe_int(get_col(row, "Luck Rank", "Luck.1", "Luck Rk")),
                # Strength of Schedule based on opponent efficiency margins
                "sos_adj_em": safe_float(get_col(row, "SOS AdjEM", "Strength of Schedule AdjEM", "SOS")),
                "sos_adj_em_rank": safe_int(get_col(row, "SOS AdjEM Rank", "SOS AdjEM.1", "SOS Rk")),
                # Average opponent offensive/defensive strength
                "sos_opp_offense": safe_float(get_col(row, "OppO", "SOS OppO", "OppO.")),
                "sos_opp_offense_rank": safe_int(get_col(row, "OppO Rank", "OppO.1", "OppO Rk")),
                "sos_opp_defense": safe_float(get_col(row, "OppD", "SOS OppD", "OppD.")),
                "sos_opp_defense_rank": safe_int(get_col(row, "OppD Rank", "OppD.1", "OppD Rk")),
                # Non-conference SOS (useful for evaluating early-season performance)
                "ncsos_adj_em": safe_float(get_col(row, "NCSOS AdjEM", "NCSOS", "NCSOS AdjEM.")),
                "ncsos_adj_em_rank": safe_int(get_col(row, "NCSOS AdjEM Rank", "NCSOS.1", "NCSOS Rk")),
                "wins": wins,
                "losses": losses,
                "conference": get_col(row, "Conf", "Conference"),
            }

            # Remove None values before insert (Supabase doesn't like explicit nulls for optional columns)
            rating_data = {k: v for k, v in rating_data.items() if v is not None}

            # Insert into Supabase (not upsert - we want historical snapshots)
            supabase.table("kenpom_ratings").insert(rating_data).execute()
            inserted += 1

            # Progress indicator for long-running inserts
            if inserted % 50 == 0:
                print(f"  Inserted {inserted} ratings...")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error storing {team_name}: {e}")

    print(f"Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def safe_int(value) -> int | None:
    """Safely convert to int."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_float(value) -> float | None:
    """Safely convert to float."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_team_kenpom_rating(team_id: str, season: int = 2025, use_cache: bool = True) -> dict | None:
    """
    Get the latest KenPom rating for a team with caching.

    Caches individual team ratings for 1 hour.

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
    result = supabase.table("kenpom_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()

    if result.data:
        # Cache the result
        ratings_cache.set("kenpom_team", result.data[0], **cache_key_kwargs)
        logger.debug(f"Cache SET: kenpom_team (team_id={team_id[:8]}..., season={season})")
        return result.data[0]

    return None


def invalidate_kenpom_cache() -> dict:
    """
    Invalidate all KenPom-related caches.

    Call this before fetching fresh data to ensure no stale data is served.

    Returns:
        Dict with counts of invalidated entries
    """
    ratings_count = ratings_cache.invalidate("kenpom_ratings")
    team_count = ratings_cache.invalidate("kenpom_team")

    logger.info(f"KenPom cache invalidated: ratings={ratings_count}, teams={team_count}")

    return {
        "ratings_invalidated": ratings_count,
        "teams_invalidated": team_count,
    }


def refresh_kenpom_data(season: int = 2025) -> dict:
    """
    Full refresh of KenPom data.

    Invalidates cache before fetching fresh data.

    Args:
        season: Season year to fetch

    Returns:
        Results dict
    """
    print("=" * 60)
    print("KenPom Data Refresh")
    print(f"Season: {season}")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "season": season,
        "status": "success",
    }

    # Invalidate cache before refresh
    cache_results = invalidate_kenpom_cache()
    results["cache_invalidated"] = cache_results
    print(f"Cache invalidated: {cache_results}")

    # Fetch ratings (bypass cache since we just invalidated)
    df = fetch_kenpom_ratings(season, use_cache=False)

    if df is None or len(df) == 0:
        results["status"] = "error"
        results["error"] = "Failed to fetch KenPom data"
        return results

    # Store in database
    store_results = store_kenpom_ratings(df, season)
    results["ratings"] = store_results

    print("\n" + "=" * 60)
    print("KenPom Refresh Complete")
    print("=" * 60)

    return results


if __name__ == "__main__":
    import json

    # Default to current season
    season = 2025

    # Allow season override via command line
    if len(sys.argv) > 1:
        try:
            season = int(sys.argv[1])
        except ValueError:
            print(f"Invalid season: {sys.argv[1]}")
            sys.exit(1)

    results = refresh_kenpom_data(season)
    print("\nResults:")
    print(json.dumps(results, indent=2))

"""
KenPom Data Scraper

Fetches advanced analytics from KenPom using kenpompy.
Requires a KenPom subscription.

Usage:
    python -m backend.data_collection.kenpom_scraper

Environment variables:
    KENPOM_EMAIL - Your KenPom account email
    KENPOM_PASSWORD - Your KenPom account password
"""

import logging
import os
import sys
from datetime import datetime
from typing import Optional

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
    """Normalize team name for matching with our database."""
    if not name:
        return ""

    # KenPom uses specific naming conventions
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


def get_team_id(team_name: str) -> Optional[str]:
    """Get team ID from our database by matching normalized name."""
    normalized = normalize_team_name(team_name)
    if not normalized:
        return None

    # Try exact match
    result = supabase.table("teams").select("id").eq("normalized_name", normalized).execute()
    if result.data:
        return result.data[0]["id"]

    # Try partial match
    result = supabase.table("teams").select("id, normalized_name").ilike(
        "normalized_name", f"%{normalized}%"
    ).execute()
    if result.data:
        return result.data[0]["id"]

    # Try without state suffix
    if "-state" in normalized:
        base_name = normalized.replace("-state", "")
        result = supabase.table("teams").select("id").ilike(
            "normalized_name", f"%{base_name}%"
        ).execute()
        if result.data:
            return result.data[0]["id"]

    return None


def _fetch_kenpom_ratings_uncached(season: int = 2025) -> Optional[pd.DataFrame]:
    """
    Internal function to fetch KenPom ratings without caching.

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)

    Returns:
        DataFrame with KenPom ratings or None if failed
    """
    if not KENPOM_EMAIL or not KENPOM_PASSWORD:
        print("ERROR: KENPOM_EMAIL and KENPOM_PASSWORD must be set")
        return None

    try:
        from kenpompy.utils import login
        import kenpompy.misc as kp

        print(f"Logging into KenPom as {KENPOM_EMAIL}...")
        browser = login(KENPOM_EMAIL, KENPOM_PASSWORD)

        print(f"Fetching Pomeroy ratings for {season}...")
        # get_pomeroy_ratings returns the main ratings table with rank, AdjEM, AdjO, AdjD, etc.
        ratings = kp.get_pomeroy_ratings(browser, season=str(season))

        print(f"Fetched {len(ratings)} team ratings")
        print(f"Columns available: {list(ratings.columns)}")
        if len(ratings) > 0:
            print(f"Sample row: {ratings.iloc[0].to_dict()}")
        browser.close()

        return ratings

    except ImportError as e:
        print(f"Import error - make sure kenpompy and selenium are installed: {e}")
        return None
    except Exception as e:
        print(f"Error fetching KenPom data: {e}")
        return None


def fetch_kenpom_ratings(season: int = 2025, use_cache: bool = True) -> Optional[pd.DataFrame]:
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


def fetch_kenpom_fourfactors(season: int = 2025) -> Optional[pd.DataFrame]:
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
    Store KenPom ratings in Supabase.

    Args:
        df: DataFrame from kenpompy
        season: Season year

    Returns:
        Dict with counts of inserted/skipped/errors
    """
    print(f"\n=== Storing KenPom Ratings ===")

    # Debug: Print actual column names from kenpompy
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
                if skipped <= 5:
                    print(f"  Could not match team: {team_name}")
                continue

            # Parse the data - column names from get_pomeroy_ratings
            # Typical columns: Rk, Team, Conf, W-L, AdjEM, AdjO, AdjO Rank, AdjD, AdjD Rank,
            # AdjT, AdjT Rank, Luck, Luck Rank, SOS AdjEM, SOS AdjEM Rank, OppO, OppO Rank,
            # OppD, OppD Rank, NCSOS AdjEM, NCSOS AdjEM Rank

            # Try multiple possible column name formats
            def get_col(row, *names):
                """Try multiple column names and return first match."""
                for name in names:
                    val = row.get(name)
                    if val is not None and str(val) != 'nan':
                        return val
                return None

            # Parse W-L record
            wl = str(get_col(row, "W-L", "W-L.1", "Record") or "0-0")
            wins = safe_int(wl.split("-")[0]) if "-" in wl else 0
            losses = safe_int(wl.split("-")[-1]) if "-" in wl else 0

            rating_data = {
                "team_id": team_id,
                "season": season,
                "captured_date": datetime.now().date().isoformat(),
                "rank": safe_int(get_col(row, "Rk", "Rank", "Rk.")),
                "adj_efficiency_margin": safe_float(get_col(row, "AdjEM", "AdjEM.", "NetRtg")),
                "adj_offense": safe_float(get_col(row, "AdjO", "AdjO.", "AdjOE")),
                "adj_offense_rank": safe_int(get_col(row, "AdjO Rank", "AdjO.1", "AdjO Rk")),
                "adj_defense": safe_float(get_col(row, "AdjD", "AdjD.", "AdjDE")),
                "adj_defense_rank": safe_int(get_col(row, "AdjD Rank", "AdjD.1", "AdjD Rk")),
                "adj_tempo": safe_float(get_col(row, "AdjT", "AdjT.", "AdjTempo")),
                "adj_tempo_rank": safe_int(get_col(row, "AdjT Rank", "AdjT.1", "AdjT Rk")),
                "luck": safe_float(get_col(row, "Luck", "Luck.")),
                "luck_rank": safe_int(get_col(row, "Luck Rank", "Luck.1", "Luck Rk")),
                "sos_adj_em": safe_float(get_col(row, "SOS AdjEM", "Strength of Schedule AdjEM", "SOS")),
                "sos_adj_em_rank": safe_int(get_col(row, "SOS AdjEM Rank", "SOS AdjEM.1", "SOS Rk")),
                "sos_opp_offense": safe_float(get_col(row, "OppO", "SOS OppO", "OppO.")),
                "sos_opp_offense_rank": safe_int(get_col(row, "OppO Rank", "OppO.1", "OppO Rk")),
                "sos_opp_defense": safe_float(get_col(row, "OppD", "SOS OppD", "OppD.")),
                "sos_opp_defense_rank": safe_int(get_col(row, "OppD Rank", "OppD.1", "OppD Rk")),
                "ncsos_adj_em": safe_float(get_col(row, "NCSOS AdjEM", "NCSOS", "NCSOS AdjEM.")),
                "ncsos_adj_em_rank": safe_int(get_col(row, "NCSOS AdjEM Rank", "NCSOS.1", "NCSOS Rk")),
                "wins": wins,
                "losses": losses,
                "conference": get_col(row, "Conf", "Conference"),
            }

            # Remove None values
            rating_data = {k: v for k, v in rating_data.items() if v is not None}

            # Insert into Supabase
            supabase.table("kenpom_ratings").insert(rating_data).execute()
            inserted += 1

            if inserted % 50 == 0:
                print(f"  Inserted {inserted} ratings...")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error storing {team_name}: {e}")

    print(f"Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")
    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def safe_int(value) -> Optional[int]:
    """Safely convert to int."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_float(value) -> Optional[float]:
    """Safely convert to float."""
    if pd.isna(value) or value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def get_team_kenpom_rating(team_id: str, season: int = 2025, use_cache: bool = True) -> Optional[dict]:
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

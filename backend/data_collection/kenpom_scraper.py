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

import os
import sys
from datetime import datetime
from typing import Optional

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

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


def fetch_kenpom_ratings(season: int = 2025) -> Optional[pd.DataFrame]:
    """
    Fetch KenPom efficiency ratings for a season.

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
        import kenpompy.summary as kp

        print(f"Logging into KenPom as {KENPOM_EMAIL}...")
        browser = login(KENPOM_EMAIL, KENPOM_PASSWORD)

        print(f"Fetching efficiency ratings for {season}...")
        efficiency = kp.get_efficiency(browser, season=str(season))

        print(f"Fetched {len(efficiency)} team ratings")
        browser.close()

        return efficiency

    except ImportError as e:
        print(f"Import error - make sure kenpompy and selenium are installed: {e}")
        return None
    except Exception as e:
        print(f"Error fetching KenPom data: {e}")
        return None


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

            # Parse the data - column names may vary by kenpompy version
            rating_data = {
                "team_id": team_id,
                "season": season,
                "captured_date": datetime.now().date().isoformat(),
                "rank": safe_int(row.get("Rk", row.get("Rank"))),
                "adj_efficiency_margin": safe_float(row.get("AdjEM", row.get("NetRtg"))),
                "adj_offense": safe_float(row.get("AdjO", row.get("AdjOE"))),
                "adj_offense_rank": safe_int(row.get("AdjO.1", row.get("AdjOE Rank"))),
                "adj_defense": safe_float(row.get("AdjD", row.get("AdjDE"))),
                "adj_defense_rank": safe_int(row.get("AdjD.1", row.get("AdjDE Rank"))),
                "adj_tempo": safe_float(row.get("AdjT", row.get("AdjTempo"))),
                "adj_tempo_rank": safe_int(row.get("AdjT.1", row.get("AdjTempo Rank"))),
                "luck": safe_float(row.get("Luck")),
                "luck_rank": safe_int(row.get("Luck.1", row.get("Luck Rank"))),
                "sos_adj_em": safe_float(row.get("SOS AdjEM", row.get("SOS"))),
                "sos_adj_em_rank": safe_int(row.get("SOS AdjEM.1", row.get("SOS Rank"))),
                "sos_opp_offense": safe_float(row.get("SOS OppO")),
                "sos_opp_offense_rank": safe_int(row.get("SOS OppO.1")),
                "sos_opp_defense": safe_float(row.get("SOS OppD")),
                "sos_opp_defense_rank": safe_int(row.get("SOS OppD.1")),
                "ncsos_adj_em": safe_float(row.get("NCSOS AdjEM", row.get("NCSOS"))),
                "ncsos_adj_em_rank": safe_int(row.get("NCSOS AdjEM.1", row.get("NCSOS Rank"))),
                "wins": safe_int(str(row.get("W-L", "0-0")).split("-")[0]),
                "losses": safe_int(str(row.get("W-L", "0-0")).split("-")[-1]),
                "conference": row.get("Conf", row.get("Conference")),
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


def get_team_kenpom_rating(team_id: str, season: int = 2025) -> Optional[dict]:
    """
    Get the latest KenPom rating for a team.

    Args:
        team_id: Team UUID
        season: Season year

    Returns:
        Dict with KenPom data or None
    """
    result = supabase.table("kenpom_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()

    if result.data:
        return result.data[0]
    return None


def refresh_kenpom_data(season: int = 2025) -> dict:
    """
    Full refresh of KenPom data.

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

    # Fetch ratings
    df = fetch_kenpom_ratings(season)

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

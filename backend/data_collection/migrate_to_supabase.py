"""
Migrate existing CSV data to Supabase.

This script loads the historical game data and rankings from CSV files
and inserts them into the Supabase database.

Usage:
    python -m backend.data_collection.migrate_to_supabase
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# Supabase client
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Paths
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"


def normalize_team_name(name: str) -> str:
    """Normalize team name for matching."""
    if pd.isna(name):
        return ""

    # Remove common suffixes
    suffixes = [
        "Wildcats", "Tigers", "Bears", "Eagles", "Bulldogs", "Cardinals",
        "Cougars", "Ducks", "Gators", "Hawks", "Huskies", "Jayhawks",
        "Knights", "Lions", "Longhorns", "Mountaineers", "Panthers",
        "Seminoles", "Spartans", "Tar Heels", "Terrapins", "Volunteers",
        "Wolverines", "Blue Devils", "Crimson Tide", "Fighting Irish",
        "Hoosiers", "Boilermakers", "Buckeyes", "Nittany Lions",
        "Golden Gophers", "Badgers", "Hawkeyes", "Cornhuskers",
        "Razorbacks", "Gamecocks", "Commodores", "Rebels", "Aggies",
        "Demon Deacons", "Hokies", "Cavaliers", "Orange", "Yellow Jackets",
        "Wolfpack", "Hurricanes", "Owls", "Pirates", "49ers",
    ]

    result = str(name).strip()
    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[:-len(suffix)].strip()
            break

    return result.lower().replace(" ", "-").replace("'", "").replace(".", "")


def get_or_create_team(name: str, conference: str = None) -> dict:
    """Get team by name or create if not exists."""
    normalized = normalize_team_name(name)

    # Check if exists
    result = supabase.table("teams").select("*").eq("normalized_name", normalized).execute()

    if result.data:
        return result.data[0]

    # Create new team
    power_conferences = {"ACC", "Big Ten", "Big 12", "SEC", "Big East", "Pac-12"}

    team_data = {
        "name": name,
        "normalized_name": normalized,
        "conference": conference,
        "is_power_conference": conference in power_conferences if conference else False,
    }

    result = supabase.table("teams").insert(team_data).execute()
    return result.data[0]


def migrate_teams():
    """Extract unique teams from games and create team records."""
    print("\n=== Migrating Teams ===")

    games_file = DATA_DIR / "games_2020_2024.csv"
    if not games_file.exists():
        print(f"Games file not found: {games_file}")
        return

    df = pd.read_csv(games_file)

    # Get unique teams from home and away
    home_teams = df[["home_team", "home_conference"]].drop_duplicates()
    home_teams.columns = ["name", "conference"]

    away_teams = df[["away_team", "away_conference"]].drop_duplicates()
    away_teams.columns = ["name", "conference"]

    all_teams = pd.concat([home_teams, away_teams]).drop_duplicates(subset=["name"])

    print(f"Found {len(all_teams)} unique teams")

    created = 0
    for _, row in all_teams.iterrows():
        if pd.notna(row["name"]):
            get_or_create_team(row["name"], row.get("conference"))
            created += 1

    print(f"Created/verified {created} teams")


def migrate_games():
    """Migrate games from CSV to Supabase."""
    print("\n=== Migrating Games ===")

    games_file = DATA_DIR / "games_2020_2024.csv"
    if not games_file.exists():
        print(f"Games file not found: {games_file}")
        return

    df = pd.read_csv(games_file)
    print(f"Loaded {len(df)} games from CSV")

    # Get all teams (we'll need their IDs)
    teams_result = supabase.table("teams").select("id, normalized_name").execute()
    team_map = {t["normalized_name"]: t["id"] for t in teams_result.data}

    migrated = 0
    skipped = 0
    errors = 0

    for _, row in df.iterrows():
        try:
            home_norm = normalize_team_name(row["home_team"])
            away_norm = normalize_team_name(row["away_team"])

            home_team_id = team_map.get(home_norm)
            away_team_id = team_map.get(away_norm)

            if not home_team_id or not away_team_id:
                skipped += 1
                continue

            # Parse date
            game_date = row.get("date")
            if pd.isna(game_date):
                game_date = None
            else:
                # Try to parse various date formats
                try:
                    game_date = pd.to_datetime(game_date).strftime("%Y-%m-%d")
                except:
                    game_date = None

            game_data = {
                "external_id": str(row.get("game_id", "")),
                "date": game_date,
                "season": int(row["season"]) if pd.notna(row.get("season")) else 2024,
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_score": int(row["home_score"]) if pd.notna(row.get("home_score")) else None,
                "away_score": int(row["away_score"]) if pd.notna(row.get("away_score")) else None,
                "is_conference_game": bool(row.get("same_conference", False)),
                "status": "final" if pd.notna(row.get("home_score")) else "scheduled",
            }

            # Upsert game
            supabase.table("games").upsert(
                game_data,
                on_conflict="external_id"
            ).execute()

            migrated += 1

            if migrated % 500 == 0:
                print(f"  Migrated {migrated} games...")

        except Exception as e:
            errors += 1
            if errors < 5:
                print(f"  Error migrating game: {e}")

    print(f"Migrated {migrated} games, skipped {skipped}, errors {errors}")


def migrate_rankings():
    """Migrate AP rankings from CSV to Supabase."""
    print("\n=== Migrating Rankings ===")

    rankings_file = DATA_DIR / "ap_rankings_final.csv"
    if not rankings_file.exists():
        print(f"Rankings file not found: {rankings_file}")
        return

    df = pd.read_csv(rankings_file)
    print(f"Loaded {len(df)} ranking entries from CSV")

    # Get all teams
    teams_result = supabase.table("teams").select("id, normalized_name").execute()
    team_map = {t["normalized_name"]: t["id"] for t in teams_result.data}

    migrated = 0
    skipped = 0

    for _, row in df.iterrows():
        try:
            team_norm = normalize_team_name(row["team"])
            team_id = team_map.get(team_norm)

            if not team_id:
                # Try to find team by creating it
                team = get_or_create_team(row["team"], row.get("conference"))
                team_id = team["id"]
                team_map[normalize_team_name(row["team"])] = team_id

            ranking_data = {
                "team_id": team_id,
                "season": int(row["season"]),
                "week": 0,  # Final/preseason ranking
                "rank": int(row["rank"]) if pd.notna(row.get("rank")) else None,
                "poll_type": "ap",
            }

            supabase.table("rankings").upsert(
                ranking_data,
                on_conflict="team_id,season,week,poll_type"
            ).execute()

            migrated += 1

        except Exception as e:
            skipped += 1
            if skipped < 5:
                print(f"  Error migrating ranking: {e}")

    print(f"Migrated {migrated} rankings, skipped {skipped}")


def migrate_spreads():
    """Migrate current spreads from CSV to Supabase."""
    print("\n=== Migrating Spreads ===")

    spreads_file = DATA_DIR / "current_spreads.csv"
    if not spreads_file.exists():
        print(f"Spreads file not found: {spreads_file}")
        return

    df = pd.read_csv(spreads_file)
    print(f"Loaded {len(df)} spread entries from CSV")

    # We need to match spreads to games, which requires finding games by teams
    # For now, just print info - spreads will be fetched fresh from The Odds API
    print("Note: Historical spreads should be fetched from The Odds API")
    print("      This CSV contains current spreads only")


def verify_migration():
    """Print verification stats."""
    print("\n=== Migration Verification ===")

    # Count teams
    teams = supabase.table("teams").select("id", count="exact").execute()
    print(f"Teams: {teams.count}")

    # Count games
    games = supabase.table("games").select("id", count="exact").execute()
    print(f"Games: {games.count}")

    # Count rankings
    rankings = supabase.table("rankings").select("id", count="exact").execute()
    print(f"Rankings: {rankings.count}")

    # Count by season
    print("\nGames by season:")
    for season in [2020, 2021, 2022, 2023, 2024]:
        season_games = supabase.table("games").select("id", count="exact").eq("season", season).execute()
        print(f"  {season}: {season_games.count}")

    # Count conference games
    conf_games = supabase.table("games").select("id", count="exact").eq("is_conference_game", True).execute()
    print(f"\nConference games: {conf_games.count}")


def main():
    print("=" * 60)
    print("Conference Contrarian - Data Migration to Supabase")
    print("=" * 60)

    # Run migrations in order
    migrate_teams()
    migrate_games()
    migrate_rankings()
    migrate_spreads()

    # Verify
    verify_migration()

    print("\n" + "=" * 60)
    print("Migration complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

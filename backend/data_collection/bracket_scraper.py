"""
ESPN Tournament Bracket Scraper

Scrapes the NCAA Tournament bracket from ESPN's public API to populate
tournament seeds (team, seed, region) and mark games as tournament games.

ESPN API provides:
- Seeds via competitors[].curatedRank.current
- Regions via notes[].headline ("Midwest Region - 1st Round")
- Round info parsed from the same notes headline

Usage:
    python -m backend.data_collection.bracket_scraper
    python -m backend.data_collection.bracket_scraper --season 2026

Can also be triggered via API endpoint: POST /refresh (future integration)
"""

import os
import re
import logging
import time
from datetime import date, datetime, timedelta
from typing import Optional

import requests
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

EASTERN_TZ = ZoneInfo("America/New_York")

# ESPN API
ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

# ============================================
# Round + Region Parsing
# ============================================

# Map ESPN headline fragments to our tournament_round values
ROUND_MAP = {
    "first four": "first_four",
    "1st round": "round_64",
    "2nd round": "round_32",
    "sweet 16": "sweet_16",
    "elite eight": "elite_8",
    "elite 8": "elite_8",
    "final four": "final_4",
    "national championship": "championship",
    "championship": "championship",
    "national semifinal": "final_4",
}

VALID_REGIONS = {"East", "West", "South", "Midwest"}


def parse_region_and_round(notes: list[dict]) -> tuple[Optional[str], Optional[str]]:
    """
    Parse region and round from ESPN event notes.

    ESPN format: "Men's Basketball Championship - Midwest Region - 1st Round"
    Returns: (region, tournament_round) e.g. ("Midwest", "round_64")
    """
    region = None
    tournament_round = None

    for note in notes:
        headline = note.get("headline", "")
        if not headline:
            continue

        headline_lower = headline.lower()

        # Extract region
        for r in VALID_REGIONS:
            if r.lower() in headline_lower:
                region = r
                break

        # Extract round
        for pattern, round_value in ROUND_MAP.items():
            if pattern in headline_lower:
                tournament_round = round_value
                break

    return region, tournament_round


# ============================================
# ESPN API Fetching
# ============================================

def fetch_tournament_games(season: int) -> list[dict]:
    """
    Fetch all tournament games from ESPN's API by scanning the tournament date range.

    Uses groups=100 to filter to NCAA tournament games only.
    Scans from mid-March through early April to cover First Four through Championship.

    Returns list of dicts with: team names, seeds, region, round, ESPN game ID.
    """
    # Tournament typically spans March 15 - April 10
    start_date = date(season, 3, 15)
    end_date = date(season, 4, 10)

    all_games = []
    seen_game_ids = set()
    current_date = start_date

    print(f"=== Scanning ESPN for {season} NCAA Tournament games ===")
    print(f"Date range: {start_date} to {end_date}")

    while current_date <= end_date:
        date_str = current_date.strftime("%Y%m%d")

        try:
            response = requests.get(
                ESPN_API_URL,
                params={"dates": date_str, "groups": 100, "limit": 200},
                headers=HEADERS,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            events = data.get("events", [])
            day_count = 0

            for event in events:
                try:
                    espn_id = event.get("id")
                    if not espn_id or espn_id in seen_game_ids:
                        continue
                    seen_game_ids.add(espn_id)

                    # Get competition data
                    competitions = event.get("competitions", [])
                    if not competitions:
                        continue
                    competition = competitions[0]
                    competitors = competition.get("competitors", [])

                    # Parse region and round from competition notes
                    # Notes live on competitions[0], not on the event
                    notes = competition.get("notes", []) or event.get("notes", [])
                    region, tournament_round = parse_region_and_round(notes)
                    if len(competitors) != 2:
                        continue

                    teams = {}
                    for competitor in competitors:
                        team_info = competitor.get("team", {})
                        home_away = competitor.get("homeAway", "")
                        seed = competitor.get("curatedRank", {}).get("current")

                        # ESPN uses display name like "Houston Cougars"
                        display_name = team_info.get("displayName", "")
                        # location is just "Houston"
                        location = team_info.get("location", "")

                        teams[home_away] = {
                            "display_name": display_name,
                            "location": location,
                            "espn_id": team_info.get("id"),
                            "abbreviation": team_info.get("abbreviation", ""),
                            "seed": seed,
                        }

                    if "home" not in teams or "away" not in teams:
                        continue

                    # Game status
                    status_type = event.get("status", {}).get("type", {})
                    game_status = status_type.get("name", "STATUS_SCHEDULED")

                    # Scores
                    home_score = None
                    away_score = None
                    if game_status in ("STATUS_FINAL", "STATUS_FINAL_OT"):
                        for competitor in competitors:
                            score = competitor.get("score")
                            if score and competitor.get("homeAway") == "home":
                                home_score = int(score)
                            elif score and competitor.get("homeAway") == "away":
                                away_score = int(score)

                    game_data = {
                        "espn_id": espn_id,
                        "date": current_date.isoformat(),
                        "home_team": teams["home"]["display_name"],
                        "home_location": teams["home"]["location"],
                        "home_abbreviation": teams["home"]["abbreviation"],
                        "home_seed": teams["home"]["seed"],
                        "away_team": teams["away"]["display_name"],
                        "away_location": teams["away"]["location"],
                        "away_abbreviation": teams["away"]["abbreviation"],
                        "away_seed": teams["away"]["seed"],
                        "region": region,
                        "tournament_round": tournament_round,
                        "game_status": game_status,
                        "home_score": home_score,
                        "away_score": away_score,
                    }

                    all_games.append(game_data)
                    day_count += 1

                except Exception as e:
                    logger.warning(f"Error parsing ESPN tournament event: {e}")
                    continue

            if day_count > 0:
                print(f"  {current_date}: {day_count} tournament games")

        except requests.exceptions.RequestException as e:
            logger.warning(f"ESPN API error for {current_date}: {e}")

        current_date += timedelta(days=1)
        time.sleep(0.5)  # Rate limit: 2 requests/sec

    print(f"Total: {len(all_games)} tournament games found")
    return all_games


def extract_seeds_from_games(games: list[dict]) -> list[dict]:
    """
    Extract unique team seed assignments from tournament game data.

    A team's seed and region come from their first tournament appearance.
    Play-in teams are identified by having a 'first_four' round.

    Returns list of dicts ready for bulk_insert_seeds.
    """
    seen_teams = {}  # location -> seed_data
    first_four_seeds = {}  # region+seed -> count (to detect play-in matchups)

    for game in games:
        for side in ("home", "away"):
            location = game[f"{side}_location"]
            seed = game[f"{side}_seed"]
            region = game.get("region")
            tournament_round = game.get("tournament_round")

            if not location or seed is None or not region:
                continue

            # Track play-in matchup numbering
            if tournament_round == "first_four":
                key = f"{region}-{seed}"
                first_four_seeds[key] = first_four_seeds.get(key, 0) + 1

            # First appearance wins (earliest round is most reliable)
            if location not in seen_teams:
                seen_teams[location] = {
                    "display_name": game[f"{side}_team"],
                    "location": location,
                    "abbreviation": game[f"{side}_abbreviation"],
                    "seed": seed,
                    "region": region,
                    "is_play_in": tournament_round == "first_four",
                }

    # Assign play_in_matchup numbers (1 or 2) for First Four teams
    play_in_counters = {}  # region+seed -> next number
    seeds = []
    for team_data in seen_teams.values():
        if team_data["is_play_in"]:
            key = f"{team_data['region']}-{team_data['seed']}"
            num = play_in_counters.get(key, 0) + 1
            play_in_counters[key] = num
            team_data["play_in_matchup"] = num if num <= 2 else None
        else:
            team_data["play_in_matchup"] = None
        seeds.append(team_data)

    return seeds


# ============================================
# Supabase Integration
# ============================================

def store_bracket_data(season: int, games: list[dict], seeds: list[dict]) -> dict:
    """
    Store tournament bracket data in Supabase:
    1. Create/get tournament row
    2. Upsert seeds (team → seed + region)
    3. Mark games as tournament games with round info

    Returns summary dict with counts.
    """
    try:
        from backend.api.supabase_client import (
            get_tournament,
            create_tournament,
            update_tournament,
            bulk_insert_seeds,
            get_team_by_name,
            get_supabase,
            normalize_team_name,
        )
    except ImportError:
        from ..api.supabase_client import (
            get_tournament,
            create_tournament,
            update_tournament,
            bulk_insert_seeds,
            get_team_by_name,
            get_supabase,
            normalize_team_name,
        )

    client = get_supabase()

    # 1. Create or get tournament
    tournament = get_tournament(season)
    if not tournament:
        tournament = create_tournament(season)
        print(f"Created tournament for {season}")
    tournament_id = tournament["id"]

    # 2. Resolve team names and insert seeds
    seeds_to_insert = []
    seed_errors = []

    for seed_data in seeds:
        # Try multiple name formats to find the team
        team = None
        names_tried = []

        # Try display name (e.g., "Houston Cougars")
        team = get_team_by_name(seed_data["display_name"])
        names_tried.append(seed_data["display_name"])

        # Try location only (e.g., "Houston")
        if not team:
            team = get_team_by_name(seed_data["location"])
            names_tried.append(seed_data["location"])

        # Try abbreviation (e.g., "HOU")
        if not team:
            team = get_team_by_name(seed_data["abbreviation"])
            names_tried.append(seed_data["abbreviation"])

        # Try normalized name lookup
        if not team:
            normalized = normalize_team_name(seed_data["location"])
            result = client.table("teams").select("id").eq(
                "normalized_name", normalized
            ).execute()
            if result.data:
                team = result.data[0]
            names_tried.append(f"normalized:{normalized}")

        if not team:
            seed_errors.append({
                "team": seed_data["display_name"],
                "seed": seed_data["seed"],
                "region": seed_data["region"],
                "names_tried": names_tried,
            })
            continue

        seeds_to_insert.append({
            "team_id": team["id"],
            "seed": seed_data["seed"],
            "region": seed_data["region"],
            "is_play_in": seed_data["is_play_in"],
            "play_in_matchup": seed_data["play_in_matchup"],
        })

    inserted_seeds = []
    if seeds_to_insert:
        inserted_seeds = bulk_insert_seeds(tournament_id, seeds_to_insert)
        print(f"Inserted/updated {len(inserted_seeds)} seeds")

    if seed_errors:
        print(f"WARNING: {len(seed_errors)} teams not found in database:")
        for err in seed_errors[:10]:
            print(f"  - {err['team']} (#{err['seed']} {err['region']}) - tried: {err['names_tried']}")

    # 3. Mark games as tournament games
    games_updated = 0
    for game in games:
        if not game.get("tournament_round"):
            continue

        # Find the game by ESPN external ID
        result = client.table("games").select("id").eq(
            "external_id", game["espn_id"]
        ).execute()

        if result.data:
            game_id = result.data[0]["id"]
            client.table("games").update({
                "is_tournament": True,
                "tournament_round": game["tournament_round"],
            }).eq("id", game_id).execute()
            games_updated += 1

    print(f"Marked {games_updated} games as tournament games")

    # 4. Update tournament status
    if len(inserted_seeds) > 0:
        update_tournament(tournament_id, {"status": "bracket_set"})

    results = {
        "season": season,
        "tournament_id": tournament_id,
        "total_games_found": len(games),
        "seeds_inserted": len(inserted_seeds),
        "seed_errors": len(seed_errors),
        "games_marked_tournament": games_updated,
        "unresolved_teams": [e["team"] for e in seed_errors],
    }

    return results


# ============================================
# Main Entry Point
# ============================================

def refresh_tournament_bracket(season: Optional[int] = None) -> dict:
    """
    Full bracket refresh: fetch from ESPN, extract seeds, store in Supabase.

    Args:
        season: Tournament year (defaults to current year)

    Returns:
        Summary dict with counts and any errors
    """
    if season is None:
        season = datetime.now(EASTERN_TZ).year

    print(f"\n{'='*60}")
    print(f"TOURNAMENT BRACKET REFRESH - {season}")
    print(f"{'='*60}\n")

    # Step 1: Fetch all tournament games from ESPN
    games = fetch_tournament_games(season)
    if not games:
        print("No tournament games found. Bracket may not be set yet.")
        return {
            "season": season,
            "status": "no_games_found",
            "total_games_found": 0,
        }

    # Step 2: Extract seed assignments
    seeds = extract_seeds_from_games(games)
    print(f"\nExtracted {len(seeds)} unique team seeds")

    # Print seed summary
    regions = {}
    for s in seeds:
        regions.setdefault(s["region"], []).append(s)
    for region, region_seeds in sorted(regions.items()):
        print(f"  {region}: {len(region_seeds)} teams")
        for s in sorted(region_seeds, key=lambda x: x["seed"]):
            pi = " (Play-In)" if s["is_play_in"] else ""
            print(f"    #{s['seed']:>2} {s['location']}{pi}")

    # Step 3: Store in Supabase
    print(f"\nStoring bracket data in Supabase...")
    results = store_bracket_data(season, games, seeds)

    print(f"\n{'='*60}")
    print(f"BRACKET REFRESH COMPLETE")
    print(f"  Seeds: {results['seeds_inserted']}")
    print(f"  Games marked: {results['games_marked_tournament']}")
    if results['seed_errors'] > 0:
        print(f"  Errors: {results['seed_errors']} teams not found")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape NCAA Tournament bracket from ESPN")
    parser.add_argument("--season", type=int, default=None, help="Tournament year (default: current)")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print only, don't store")
    args = parser.parse_args()

    season = args.season or datetime.now(EASTERN_TZ).year

    if args.dry_run:
        print(f"DRY RUN - Fetching {season} tournament data from ESPN...")
        games = fetch_tournament_games(season)
        seeds = extract_seeds_from_games(games)
        print(f"\n{len(seeds)} teams found:")
        for s in sorted(seeds, key=lambda x: (x["region"], x["seed"])):
            pi = " (PI)" if s["is_play_in"] else ""
            print(f"  {s['region']:>8} #{s['seed']:>2} {s['display_name']}{pi}")
    else:
        results = refresh_tournament_bracket(season)
        print(f"\nResults: {results}")

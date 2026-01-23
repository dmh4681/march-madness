"""
ESPN Schedule Scraper

Fetches real game tip times from ESPN's public API.
ESPN provides actual scheduled times while The Odds API only provides dates.

Usage:
    python -m backend.data_collection.espn_scraper

Can also be triggered via API endpoint: POST /refresh-espn-times
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional
import re

import requests
from dotenv import load_dotenv

# Timezone handling
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

# Timezones
EASTERN_TZ = ZoneInfo("America/New_York")
UTC_TZ = ZoneInfo("UTC")

# ESPN API endpoint for college basketball
ESPN_API_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"

# Team name normalization mappings (ESPN -> our normalized names)
ESPN_TEAM_MAP = {
    # Common variations
    "UConn": "connecticut",
    "Connecticut": "connecticut",
    "UConn Huskies": "connecticut",
    "UCONN": "connecticut",
    "North Carolina": "north-carolina",
    "UNC": "north-carolina",
    "NC State": "nc-state",
    "Mich St": "michigan-state",
    "Michigan St": "michigan-state",
    "Ohio St": "ohio-state",
    "Penn St": "penn-state",
    "Oklahoma St": "oklahoma-state",
    "Kansas St": "kansas-state",
    "Iowa St": "iowa-state",
    "Miss St": "mississippi-state",
    "Mississippi St": "mississippi-state",
    "Florida St": "florida-state",
    "Arizona St": "arizona-state",
    "San Diego St": "san-diego-state",
    "Boise St": "boise-state",
    "Fresno St": "fresno-state",
    "Colorado St": "colorado-state",
    "Ball St": "ball-state",
    "Kent St": "kent-state",
    "SDSU": "san-diego-state",
    "BYU": "byu",
    "USC": "usc",
    "UCLA": "ucla",
    "SMU": "smu",
    "TCU": "tcu",
    "LSU": "lsu",
    "VCU": "vcu",
    "UCF": "ucf",
    "UTEP": "utep",
    "UNLV": "unlv",
    "UAB": "uab",
    "UTSA": "utsa",
    "FIU": "fiu",
    "FAU": "fau",
    "Ole Miss": "mississippi",
    "Pitt": "pittsburgh",
    # Add more as needed
}


def normalize_espn_team_name(name: str) -> str:
    """
    Normalize ESPN team name to match our database format.
    """
    if not name:
        return ""

    # Check direct mapping first
    if name in ESPN_TEAM_MAP:
        return ESPN_TEAM_MAP[name]

    # Basic normalization
    result = name.lower()

    # Remove common suffixes/mascots
    mascots = [
        "wildcats", "tigers", "bears", "eagles", "bulldogs", "cardinals",
        "cougars", "ducks", "gators", "hawks", "huskies", "jayhawks",
        "knights", "lions", "longhorns", "mountaineers", "panthers",
        "seminoles", "spartans", "tar heels", "terrapins", "volunteers",
        "wolverines", "blue devils", "crimson tide", "fighting irish",
        "hoosiers", "boilermakers", "buckeyes", "nittany lions",
        "golden gophers", "badgers", "hawkeyes", "cornhuskers",
        "razorbacks", "gamecocks", "commodores", "rebels", "aggies",
        "bruins", "trojans", "beavers", "buffaloes", "sooners",
        "red raiders", "horned frogs", "cyclones", "golden eagles",
        "blue jays", "musketeers", "friars", "pirates", "braves",
        "bobcats", "owls", "red storm", "orange", "wolfpack", "demon deacons",
        "yellow jackets", "cavaliers", "hokies", "bearcats", "billikens",
        "redhawks", "roadrunners", "jackrabbits", "bison", "pioneers",
        "tommies", "thunderbirds", "penguins", "rockets", "falcons",
        "screaming", "golden", "fighting", "lady", "blue", "red", "black",
    ]

    for mascot in mascots:
        if result.endswith(f" {mascot}"):
            result = result[:-len(mascot)-1]
            break

    # Handle "State" abbreviations - but only if not already "state"
    # Be careful: "North Dakota State" should become "north-dakota-state", not "north-dakota-stateate"
    if " st " in result and " state" not in result:
        result = result.replace(" st ", " state ")
    if result.endswith(" st") and not result.endswith(" state"):
        result = result[:-3] + " state"

    # Convert spaces to hyphens, remove punctuation
    result = result.replace(" ", "-").replace("'", "").replace(".", "").strip("-")

    # Handle double hyphens
    while "--" in result:
        result = result.replace("--", "-")

    return result


def fetch_espn_schedule(target_date: date) -> list[dict]:
    """
    Fetch games from ESPN API for a specific date.

    Returns a list of dicts with:
        - home_team: str (normalized name)
        - away_team: str (normalized name)
        - tip_time: datetime (UTC)
        - espn_id: str
        - status: str
    """
    date_str = target_date.strftime("%Y%m%d")

    params = {
        "dates": date_str,
        "limit": 500,  # Get all games for the day
    }

    try:
        response = requests.get(ESPN_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        games = []
        events = data.get("events", [])

        for event in events:
            try:
                # Get tip time
                game_date_str = event.get("date")
                if not game_date_str:
                    continue

                # Parse ISO format date
                tip_time = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))

                # Get teams
                competitions = event.get("competitions", [])
                if not competitions:
                    continue

                competition = competitions[0]
                competitors = competition.get("competitors", [])

                if len(competitors) != 2:
                    continue

                home_team = None
                away_team = None

                for competitor in competitors:
                    team = competitor.get("team", {})
                    team_name = team.get("displayName") or team.get("name") or team.get("shortDisplayName")
                    is_home = competitor.get("homeAway") == "home"

                    normalized = normalize_espn_team_name(team_name)

                    if is_home:
                        home_team = normalized
                    else:
                        away_team = normalized

                if home_team and away_team:
                    games.append({
                        "home_team": home_team,
                        "away_team": away_team,
                        "tip_time": tip_time,
                        "espn_id": event.get("id"),
                        "status": event.get("status", {}).get("type", {}).get("name", "scheduled"),
                    })

            except Exception as e:
                logger.warning(f"Error parsing ESPN event: {e}")
                continue

        logger.info(f"Fetched {len(games)} games from ESPN for {target_date}")
        return games

    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching ESPN schedule: {e}")
        return []


def update_game_tip_times(days: int = 7) -> dict:
    """
    Update tip times in our database from ESPN data.

    Args:
        days: Number of days ahead to fetch (default 7)

    Returns:
        dict with counts of games updated, not found, etc.
    """
    from backend.api.supabase_client import get_supabase

    client = get_supabase()
    today = datetime.now(EASTERN_TZ).date()

    results = {
        "dates_processed": 0,
        "games_updated": 0,
        "games_not_found": 0,
        "games_already_have_time": 0,
        "errors": 0,
    }

    # Process each day
    for day_offset in range(days):
        target_date = today + timedelta(days=day_offset)
        results["dates_processed"] += 1

        # Fetch ESPN data for this date
        espn_games = fetch_espn_schedule(target_date)

        if not espn_games:
            continue

        # Get our games for this date
        our_games = client.table("games").select(
            "id, home_team_id, away_team_id, tip_time"
        ).eq("date", target_date.isoformat()).execute()

        if not our_games.data:
            continue

        # Build a mapping of team IDs to normalized names
        team_ids = set()
        for game in our_games.data:
            team_ids.add(game["home_team_id"])
            team_ids.add(game["away_team_id"])

        team_map = {}  # team_id -> normalized_name
        if team_ids:
            teams = client.table("teams").select("id, normalized_name").in_(
                "id", list(team_ids)
            ).execute()
            for team in teams.data:
                team_map[team["id"]] = team["normalized_name"]

        # Match and update
        for our_game in our_games.data:
            our_home = team_map.get(our_game["home_team_id"], "")
            our_away = team_map.get(our_game["away_team_id"], "")

            # Skip if we already have a real tip time
            existing_tip = our_game.get("tip_time")
            if existing_tip:
                # Check if it's a real time (not just midnight)
                try:
                    existing_dt = datetime.fromisoformat(existing_tip.replace("Z", "+00:00"))
                    if existing_dt.hour != 0 or existing_dt.minute != 0:
                        results["games_already_have_time"] += 1
                        continue
                except:
                    pass

            # Find matching ESPN game
            matched_espn = None
            for espn_game in espn_games:
                # Check if teams match (order matters: home vs away)
                espn_home = espn_game["home_team"]
                espn_away = espn_game["away_team"]

                # Try exact match first
                if our_home == espn_home and our_away == espn_away:
                    matched_espn = espn_game
                    break

                # Try partial match (e.g., "duke" matches "duke-blue-devils")
                home_match = (our_home in espn_home or espn_home in our_home or
                            our_home.split("-")[0] == espn_home.split("-")[0])
                away_match = (our_away in espn_away or espn_away in our_away or
                            our_away.split("-")[0] == espn_away.split("-")[0])

                if home_match and away_match:
                    matched_espn = espn_game
                    break

            if matched_espn:
                # Update tip time
                try:
                    tip_time_iso = matched_espn["tip_time"].isoformat()
                    client.table("games").update({
                        "tip_time": tip_time_iso
                    }).eq("id", our_game["id"]).execute()
                    results["games_updated"] += 1
                    logger.debug(f"Updated tip time for {our_away} @ {our_home}: {tip_time_iso}")
                except Exception as e:
                    logger.error(f"Error updating game {our_game['id']}: {e}")
                    results["errors"] += 1
            else:
                results["games_not_found"] += 1
                logger.debug(f"No ESPN match for {our_away} @ {our_home}")

    logger.info(f"ESPN tip time update complete: {results}")
    return results


def refresh_espn_tip_times(days: int = 7) -> dict:
    """
    Main entry point for refreshing tip times from ESPN.

    This is a lightweight operation that can run frequently.
    """
    logger.info(f"=== Refreshing ESPN Tip Times (next {days} days) ===")

    results = update_game_tip_times(days=days)

    logger.info(f"Updated {results['games_updated']} games with real tip times")
    return results


if __name__ == "__main__":
    import json
    results = refresh_espn_tip_times()
    print("\nResults:")
    print(json.dumps(results, indent=2))

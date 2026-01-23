"""
Market Matcher Service

Matches prediction market titles to games and teams in our database.
This is the tricky part - prediction markets use various naming conventions.
"""

import re
import logging
from typing import Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


# ============================================================================
# TEAM NAME ALIASES
# Maps canonical team names to common variations used in prediction markets
# ============================================================================

TEAM_ALIASES = {
    # ACC
    "Duke": ["Duke Blue Devils", "Duke", "Blue Devils"],
    "North Carolina": ["UNC", "North Carolina", "Tar Heels", "North Carolina Tar Heels", "Carolina"],
    "Virginia": ["Virginia", "Virginia Cavaliers", "UVA", "Cavaliers"],
    "Wake Forest": ["Wake Forest", "Wake Forest Demon Deacons", "Wake", "Demon Deacons"],
    "NC State": ["NC State", "North Carolina State", "Wolfpack", "N.C. State"],
    "Clemson": ["Clemson", "Clemson Tigers"],
    "Florida State": ["Florida State", "FSU", "Seminoles", "Florida St."],
    "Miami": ["Miami", "Miami Hurricanes", "Miami FL", "Miami (FL)"],
    "Syracuse": ["Syracuse", "Syracuse Orange", "Cuse"],
    "Louisville": ["Louisville", "Louisville Cardinals"],
    "Notre Dame": ["Notre Dame", "Fighting Irish"],
    "Pittsburgh": ["Pittsburgh", "Pitt", "Panthers"],
    "Boston College": ["Boston College", "BC", "Eagles"],
    "Georgia Tech": ["Georgia Tech", "GT", "Yellow Jackets"],
    "Virginia Tech": ["Virginia Tech", "VT", "Hokies"],

    # Big Ten
    "Michigan State": ["Michigan State", "MSU", "Spartans", "Mich. State", "Mich St."],
    "Michigan": ["Michigan", "Wolverines", "U-M"],
    "Ohio State": ["Ohio State", "OSU", "Buckeyes", "Ohio St."],
    "Purdue": ["Purdue", "Boilermakers", "Purdue Boilermakers"],
    "Indiana": ["Indiana", "Hoosiers", "IU"],
    "Illinois": ["Illinois", "Fighting Illini", "Illini"],
    "Wisconsin": ["Wisconsin", "Badgers"],
    "Iowa": ["Iowa", "Hawkeyes"],
    "Minnesota": ["Minnesota", "Golden Gophers", "Gophers"],
    "Northwestern": ["Northwestern", "Wildcats"],
    "Nebraska": ["Nebraska", "Cornhuskers", "Huskers"],
    "Penn State": ["Penn State", "PSU", "Nittany Lions"],
    "Maryland": ["Maryland", "Terrapins", "Terps"],
    "Rutgers": ["Rutgers", "Scarlet Knights"],
    "UCLA": ["UCLA", "Bruins"],
    "USC": ["USC", "Southern California", "Trojans", "Southern Cal"],
    "Oregon": ["Oregon", "Ducks"],
    "Washington": ["Washington", "Huskies", "UW"],

    # Big 12
    "Kansas": ["Kansas", "KU", "Jayhawks", "Kansas Jayhawks"],
    "Baylor": ["Baylor", "Bears", "Baylor Bears"],
    "Texas": ["Texas", "Longhorns", "Texas Longhorns"],
    "Texas Tech": ["Texas Tech", "Red Raiders", "TTU"],
    "TCU": ["TCU", "Horned Frogs", "Texas Christian"],
    "Oklahoma State": ["Oklahoma State", "OSU", "Cowboys", "OK State"],
    "West Virginia": ["West Virginia", "WVU", "Mountaineers"],
    "Iowa State": ["Iowa State", "ISU", "Cyclones"],
    "Kansas State": ["Kansas State", "K-State", "Wildcats"],
    "Oklahoma": ["Oklahoma", "Sooners", "OU"],
    "Houston": ["Houston", "Cougars", "Houston Cougars"],
    "Cincinnati": ["Cincinnati", "Bearcats", "Cincy"],
    "UCF": ["UCF", "Central Florida", "Knights"],
    "BYU": ["BYU", "Brigham Young", "Cougars"],
    "Arizona": ["Arizona", "Wildcats", "U of A"],
    "Arizona State": ["Arizona State", "ASU", "Sun Devils"],
    "Colorado": ["Colorado", "Buffaloes", "Buffs", "CU"],
    "Utah": ["Utah", "Utes"],

    # SEC
    "Kentucky": ["Kentucky", "UK", "Wildcats", "Kentucky Wildcats"],
    "Tennessee": ["Tennessee", "Volunteers", "Vols"],
    "Auburn": ["Auburn", "Tigers", "Auburn Tigers"],
    "Alabama": ["Alabama", "Crimson Tide", "Bama"],
    "Arkansas": ["Arkansas", "Razorbacks", "Hogs"],
    "Florida": ["Florida", "Gators", "UF"],
    "LSU": ["LSU", "Louisiana State", "Tigers"],
    "Georgia": ["Georgia", "Bulldogs", "UGA"],
    "Texas A&M": ["Texas A&M", "Aggies", "TAMU"],
    "Mississippi State": ["Mississippi State", "Miss State", "Bulldogs", "MSU"],
    "Ole Miss": ["Ole Miss", "Mississippi", "Rebels"],
    "Missouri": ["Missouri", "Mizzou", "Tigers"],
    "South Carolina": ["South Carolina", "Gamecocks", "SC"],
    "Vanderbilt": ["Vanderbilt", "Commodores", "Vandy"],

    # Big East
    "UConn": ["UConn", "Connecticut", "Huskies", "Connecticut Huskies"],
    "Marquette": ["Marquette", "Golden Eagles"],
    "Villanova": ["Villanova", "Wildcats", "Nova"],
    "Creighton": ["Creighton", "Bluejays"],
    "Xavier": ["Xavier", "Musketeers"],
    "Providence": ["Providence", "Friars"],
    "Butler": ["Butler", "Bulldogs"],
    "Seton Hall": ["Seton Hall", "Pirates"],
    "St. John's": ["St. John's", "Red Storm", "St Johns", "Saint John's"],
    "Georgetown": ["Georgetown", "Hoyas"],
    "DePaul": ["DePaul", "Blue Demons"],

    # Other Notable
    "Gonzaga": ["Gonzaga", "Zags", "Bulldogs", "Gonzaga Bulldogs"],
    "Saint Mary's": ["Saint Mary's", "St. Mary's", "Gaels"],
    "San Diego State": ["San Diego State", "SDSU", "Aztecs"],
    "Memphis": ["Memphis", "Tigers"],
    "Wichita State": ["Wichita State", "Shockers"],
    "Dayton": ["Dayton", "Flyers"],
    "VCU": ["VCU", "Virginia Commonwealth", "Rams"],
}


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for matching.

    Converts to lowercase, removes extra whitespace and punctuation.
    """
    if not name:
        return ""

    name = name.lower().strip()
    name = re.sub(r'\s+', ' ', name)

    # Remove common suffixes
    suffixes = [
        "university", "state university", "college",
    ]
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()

    # Remove punctuation
    name = re.sub(r"['\.\-]", "", name)

    return name


def match_team_name(market_name: str, db_teams: list[dict]) -> Optional[dict]:
    """
    Find best matching team from database for a name from prediction market.

    Args:
        market_name: Team name from prediction market
        db_teams: List of team dicts with 'id', 'name', 'normalized_name' fields

    Returns:
        Best matching team dict or None
    """
    if not market_name or not db_teams:
        return None

    market_normalized = normalize_team_name(market_name)

    best_match = None
    best_score = 0.0

    for team in db_teams:
        team_name = team.get("name", "")
        team_normalized = team.get("normalized_name", normalize_team_name(team_name))

        score = 0.0

        # 1. Direct normalized match
        if market_normalized == team_normalized:
            return team

        # 2. Check aliases
        for alias_key, aliases in TEAM_ALIASES.items():
            aliases_lower = [a.lower() for a in aliases]

            # Check if market name matches any alias
            if market_normalized in aliases_lower or market_name.lower() in aliases_lower:
                # Check if team name matches the canonical name or aliases
                if (alias_key.lower() in team_normalized or
                    team_name.lower() in aliases_lower or
                    any(a.lower() in team_normalized for a in aliases)):
                    return team

        # 3. Fuzzy match as fallback
        fuzzy_score = SequenceMatcher(None, market_normalized, team_normalized).ratio()

        # Boost score if first word matches (school name)
        market_first = market_normalized.split()[0] if market_normalized.split() else ""
        team_first = team_normalized.split()[0] if team_normalized.split() else ""
        if market_first and team_first and market_first == team_first:
            fuzzy_score = max(fuzzy_score, 0.75)

        # Check if market name contains team name or vice versa
        if market_normalized in team_normalized or team_normalized in market_normalized:
            fuzzy_score = max(fuzzy_score, 0.8)

        if fuzzy_score > best_score and fuzzy_score > 0.6:
            best_score = fuzzy_score
            best_match = team

    if best_match:
        logger.debug(f"Matched '{market_name}' -> '{best_match.get('name')}' (score: {best_score:.2f})")

    return best_match


def extract_game_teams(market_title: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract team names from a game market title.

    Handles various formats like:
    - "Duke vs UNC"
    - "Will Duke beat North Carolina?"
    - "Duke to defeat UNC"
    - "Duke - UNC game winner"

    Returns:
        Tuple of (team1, team2) or (None, None) if can't parse
    """
    if not market_title:
        return None, None

    # Common patterns
    patterns = [
        # "Duke vs UNC", "Duke vs. North Carolina"
        r"(.+?)\s+(?:vs\.?|versus)\s+(.+?)(?:\?|$|:|\s+game|\s+match|\s+winner)",

        # "Will Duke beat UNC?"
        r"[Ww]ill\s+(.+?)\s+beat\s+(.+?)\??",

        # "Duke to beat/defeat UNC"
        r"(.+?)\s+to\s+(?:beat|defeat)\s+(.+?)(?:\?|$)",

        # "Duke - UNC" or "Duke vs UNC game"
        r"^(.+?)\s+-\s+(.+?)(?:\s+game|\s+match)?$",

        # "Duke over UNC"
        r"(.+?)\s+over\s+(.+?)(?:\?|$)",
    ]

    for pattern in patterns:
        match = re.search(pattern, market_title, re.IGNORECASE)
        if match:
            team1 = match.group(1).strip()
            team2 = match.group(2).strip()

            # Clean up common artifacts
            for cleanup in ["?", "!", ".", ","]:
                team1 = team1.rstrip(cleanup)
                team2 = team2.rstrip(cleanup)

            return team1, team2

    return None, None


def extract_futures_team(market_title: str) -> Optional[str]:
    """
    Extract team name from a futures market title.

    Handles formats like:
    - "Duke to win NCAA Championship"
    - "Will Kansas make Final Four?"
    - "Kentucky: National Champion"
    - "Will Michigan be a number 1 seed in the 2026 NCAA..."
    """
    if not market_title:
        return None

    patterns = [
        # "Duke to win..."
        r"^(.+?)\s+to\s+win",

        # "Will Duke win/make/reach/advance/be..."
        r"[Ww]ill\s+(.+?)\s+(?:win|make|reach|advance|be\s+a)",

        # "Duke: Champion" or "Duke - Champion"
        r"^(.+?)[\:\-]\s*(?:National\s+)?Champion",

        # "Duke wins..."
        r"^(.+?)\s+wins",

        # "Can Duke win..."
        r"[Cc]an\s+(.+?)\s+win",

        # "Will Duke be a number 1 seed" - more specific pattern
        r"[Ww]ill\s+(.+?)\s+be\s+",
    ]

    for pattern in patterns:
        match = re.search(pattern, market_title, re.IGNORECASE)
        if match:
            team = match.group(1).strip()
            # Clean up
            for cleanup in ["?", "!", ".", ","]:
                team = team.rstrip(cleanup)
            return team

    return None


async def match_market_to_game(
    market: dict,
    games: list[dict],
    teams: list[dict]
) -> Optional[str]:
    """
    Match a game-type market to a game_id in our database.

    Args:
        market: Parsed market dict with 'title', 'market_type'
        games: List of games with 'id', 'home_team_id', 'away_team_id'
        teams: List of teams with 'id', 'name', 'normalized_name'

    Returns:
        game_id if matched, None otherwise
    """
    if market.get("market_type") != "game":
        return None

    team1_name, team2_name = extract_game_teams(market.get("title", ""))
    if not team1_name or not team2_name:
        return None

    team1 = match_team_name(team1_name, teams)
    team2 = match_team_name(team2_name, teams)

    if not team1 or not team2:
        logger.debug(f"Could not match teams from market: {market.get('title')}")
        return None

    team1_id = team1["id"]
    team2_id = team2["id"]

    # Find game with these teams
    for game in games:
        game_teams = {game.get("home_team_id"), game.get("away_team_id")}
        if team1_id in game_teams and team2_id in game_teams:
            logger.info(f"Matched market '{market.get('title')[:50]}...' to game {game['id'][:8]}")
            return game["id"]

    logger.debug(f"No game found for market teams: {team1.get('name')} vs {team2.get('name')}")
    return None


async def match_market_to_team(
    market: dict,
    teams: list[dict]
) -> Optional[str]:
    """
    Match a futures market to a team_id.

    Args:
        market: Parsed market dict with 'title', 'market_type', 'outcomes'
        teams: List of teams with 'id', 'name', 'normalized_name'

    Returns:
        team_id if matched, None otherwise
    """
    if market.get("market_type") not in ["futures", "prop"]:
        return None

    # Try to extract from title
    team_name = extract_futures_team(market.get("title", ""))
    if team_name:
        team = match_team_name(team_name, teams)
        if team:
            return team["id"]

    # Try outcomes (for multi-team futures)
    for outcome in market.get("outcomes", []):
        outcome_name = outcome.get("name", "")
        if outcome_name and outcome_name not in ["Yes", "No"]:
            team = match_team_name(outcome_name, teams)
            if team:
                return team["id"]

    return None


# For testing
if __name__ == "__main__":
    # Test team matching
    test_names = [
        "Duke Blue Devils",
        "UNC",
        "North Carolina Tar Heels",
        "Kentucky",
        "KU",
        "Michigan State Spartans",
        "Gonzaga Zags",
    ]

    fake_teams = [
        {"id": "1", "name": "Duke Blue Devils", "normalized_name": "duke"},
        {"id": "2", "name": "North Carolina Tar Heels", "normalized_name": "north-carolina"},
        {"id": "3", "name": "Kentucky Wildcats", "normalized_name": "kentucky"},
        {"id": "4", "name": "Kansas Jayhawks", "normalized_name": "kansas"},
        {"id": "5", "name": "Michigan State Spartans", "normalized_name": "michigan-state"},
        {"id": "6", "name": "Gonzaga Bulldogs", "normalized_name": "gonzaga"},
    ]

    print("Team matching tests:")
    for name in test_names:
        match = match_team_name(name, fake_teams)
        print(f"  '{name}' -> {match.get('name') if match else 'NO MATCH'}")

    print("\nGame extraction tests:")
    game_titles = [
        "Duke vs UNC",
        "Will Kansas beat Kentucky?",
        "Michigan State to defeat Gonzaga",
        "Duke - North Carolina game winner",
    ]
    for title in game_titles:
        t1, t2 = extract_game_teams(title)
        print(f"  '{title}' -> {t1} vs {t2}")

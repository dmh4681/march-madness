"""
Haslametrics Data Scraper

Fetches advanced analytics from Haslametrics.
FREE - No subscription required.

Uses "All-Play Percentage" methodology instead of KenPom's efficiency margin.

Usage:
    python -m backend.data_collection.haslametrics_scraper [season]

Example:
    python -m backend.data_collection.haslametrics_scraper 2025
"""

import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Optional

import requests
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

# Haslametrics XML endpoint (no auth required!)
# Format: ratings{YY}.xml where YY is the 2-digit year
HASLAMETRICS_BASE_URL = "https://haslametrics.com/ratings{season}.xml"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    sys.exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def normalize_team_name(name: str) -> str:
    """
    Normalize Haslametrics team names to match our database.

    Haslametrics uses abbreviated names (e.g., "N Carolina", "Abil. Christian").
    """
    if not name:
        return ""

    # Haslametrics-specific name mappings
    name_map = {
        "N Carolina": "north-carolina",
        "NC State": "nc-state",
        "N Carolina St": "nc-state",
        "Miami FL": "miami",
        "Miami OH": "miami-oh",
        "UConn": "connecticut",
        "Connecticut": "connecticut",
        "St. John's": "st-johns",
        "Saint John's": "st-johns",
        "St John's": "st-johns",
        "Saint Mary's": "saint-marys",
        "St. Mary's": "saint-marys",
        "St Mary's": "saint-marys",
        "Ole Miss": "mississippi",
        "Mississippi": "mississippi",
        "USC": "southern-california",
        "Southern Cal": "southern-california",
        "Southern California": "southern-california",
        "UCF": "central-florida",
        "Central Florida": "central-florida",
        "UNLV": "unlv",
        "Nevada Las Vegas": "unlv",
        "BYU": "brigham-young",
        "Brigham Young": "brigham-young",
        "LSU": "louisiana-state",
        "Louisiana St.": "louisiana-state",
        "Louisiana St": "louisiana-state",
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
        "Abil. Christian": "abilene-christian",
        "Abilene Christian": "abilene-christian",
        "S Carolina": "south-carolina",
        "South Carolina": "south-carolina",
        "W Virginia": "west-virginia",
        "West Virginia": "west-virginia",
        "W Kentucky": "western-kentucky",
        "Western Kentucky": "western-kentucky",
        "E Kentucky": "eastern-kentucky",
        "Eastern Kentucky": "eastern-kentucky",
        "N Kentucky": "northern-kentucky",
        "Northern Kentucky": "northern-kentucky",
        "S Florida": "south-florida",
        "South Florida": "south-florida",
        "C Florida": "central-florida",
        "N Texas": "north-texas",
        "North Texas": "north-texas",
        "S Alabama": "south-alabama",
        "South Alabama": "south-alabama",
        "E Carolina": "east-carolina",
        "East Carolina": "east-carolina",
        "W Michigan": "western-michigan",
        "Western Michigan": "western-michigan",
        "E Michigan": "eastern-michigan",
        "Eastern Michigan": "eastern-michigan",
        "C Michigan": "central-michigan",
        "Central Michigan": "central-michigan",
        "N Illinois": "northern-illinois",
        "Northern Illinois": "northern-illinois",
        "S Illinois": "southern-illinois",
        "Southern Illinois": "southern-illinois",
        "SE Missouri St": "southeast-missouri-state",
        "SE Missouri St.": "southeast-missouri-state",
        "SIU Edwardsville": "siu-edwardsville",
        "SIUE": "siu-edwardsville",
        "Geo Washington": "george-washington",
        "George Washington": "george-washington",
        "Geo Mason": "george-mason",
        "George Mason": "george-mason",
        "Geo. Washington": "george-washington",
        "Geo. Mason": "george-mason",
        "FIU": "florida-international",
        "Florida Intl": "florida-international",
        "FAU": "florida-atlantic",
        "Florida Atlantic": "florida-atlantic",
        "FGCU": "florida-gulf-coast",
        "Florida Gulf Coast": "florida-gulf-coast",
        "UNC Wilmington": "unc-wilmington",
        "UNC Greensboro": "unc-greensboro",
        "UNC Asheville": "unc-asheville",
        "UNC Charlotte": "charlotte",
        "Charlotte": "charlotte",
        "App State": "appalachian-state",
        "Appalachian St": "appalachian-state",
        "San Jose St": "san-jose-state",
        "San Jose St.": "san-jose-state",
        "Fresno St": "fresno-state",
        "Fresno St.": "fresno-state",
        "Boise St": "boise-state",
        "Boise St.": "boise-state",
        "Col. of Charleston": "college-of-charleston",
        "College of Charleston": "college-of-charleston",
        "Charleston": "college-of-charleston",
        "Loyola Chicago": "loyola-chicago",
        "Loyola (Chi)": "loyola-chicago",
        "Loyola MD": "loyola-maryland",
        "Loyola Marymount": "loyola-marymount",
        "LMU": "loyola-marymount",
        "St. Bonaventure": "st-bonaventure",
        "St Bonaventure": "st-bonaventure",
        "St. Joseph's": "saint-josephs",
        "St Joseph's": "saint-josephs",
        "Saint Joseph's": "saint-josephs",
        "St. Peter's": "saint-peters",
        "St Peter's": "saint-peters",
        "Saint Peter's": "saint-peters",
        "St. Francis PA": "saint-francis-pa",
        "St. Francis NY": "st-francis-brooklyn",
        "St. Francis Brooklyn": "st-francis-brooklyn",
        "UMBC": "maryland-baltimore-county",
        "MD Baltimore County": "maryland-baltimore-county",
        "UMKC": "kansas-city",
        "Kansas City": "kansas-city",
        "UT Arlington": "texas-arlington",
        "Texas Arlington": "texas-arlington",
        "UT San Antonio": "texas-san-antonio",
        "UTSA": "texas-san-antonio",
        "Texas San Antonio": "texas-san-antonio",
        "UT Rio Grande Valley": "texas-rio-grande-valley",
        "UTRGV": "texas-rio-grande-valley",
        "LA Tech": "louisiana-tech",
        "Louisiana Tech": "louisiana-tech",
        "UL Lafayette": "louisiana-lafayette",
        "UL Monroe": "louisiana-monroe",
        "Louisiana Lafayette": "louisiana-lafayette",
        "Louisiana Monroe": "louisiana-monroe",
        "Little Rock": "arkansas-little-rock",
        "Ark. Little Rock": "arkansas-little-rock",
        "Arkansas Little Rock": "arkansas-little-rock",
        "Ark. Pine Bluff": "arkansas-pine-bluff",
        "Arkansas Pine Bluff": "arkansas-pine-bluff",
        "UAPB": "arkansas-pine-bluff",
        "Prairie View": "prairie-view-am",
        "Prairie View A&M": "prairie-view-am",
        "Texas A&M CC": "texas-am-corpus-christi",
        "Texas A&M Corpus Christi": "texas-am-corpus-christi",
        "Incarnate Word": "incarnate-word",
        "UIW": "incarnate-word",
        "Nicholls St": "nicholls-state",
        "Nicholls St.": "nicholls-state",
        "Nicholls": "nicholls-state",
        "McNeese St": "mcneese-state",
        "McNeese St.": "mcneese-state",
        "McNeese": "mcneese-state",
        "Northwestern St": "northwestern-state",
        "Northwestern St.": "northwestern-state",
        "Sam Houston St": "sam-houston-state",
        "Sam Houston St.": "sam-houston-state",
        "Sam Houston": "sam-houston-state",
        "SE Louisiana": "southeastern-louisiana",
        "Southeastern Louisiana": "southeastern-louisiana",
        "New Mexico St": "new-mexico-state",
        "New Mexico St.": "new-mexico-state",
        "Utah St": "utah-state",
        "Utah St.": "utah-state",
        "Colorado St": "colorado-state",
        "Colorado St.": "colorado-state",
        "Long Beach St": "long-beach-state",
        "Long Beach St.": "long-beach-state",
        "Cal St Fullerton": "cal-state-fullerton",
        "Cal St. Fullerton": "cal-state-fullerton",
        "CSU Fullerton": "cal-state-fullerton",
        "Cal St Northridge": "cal-state-northridge",
        "Cal St. Northridge": "cal-state-northridge",
        "CSUN": "cal-state-northridge",
        "Cal St Bakersfield": "cal-state-bakersfield",
        "Cal St. Bakersfield": "cal-state-bakersfield",
        "Sacramento St": "sacramento-state",
        "Sacramento St.": "sacramento-state",
        "Cal Poly": "cal-poly",
        "Cal Poly SLO": "cal-poly",
        "UC Davis": "uc-davis",
        "UC Irvine": "uc-irvine",
        "UC Riverside": "uc-riverside",
        "UC San Diego": "uc-san-diego",
        "UC Santa Barbara": "uc-santa-barbara",
        "UCSB": "uc-santa-barbara",
        "Bowling Green": "bowling-green",
        "BGSU": "bowling-green",
        "Kent St": "kent-state",
        "Kent St.": "kent-state",
        "Ball St": "ball-state",
        "Ball St.": "ball-state",
        "Morehead St": "morehead-state",
        "Morehead St.": "morehead-state",
        "Murray St": "murray-state",
        "Murray St.": "murray-state",
        "Austin Peay": "austin-peay",
        "Tenn. Tech": "tennessee-tech",
        "Tennessee Tech": "tennessee-tech",
        "Tenn. St.": "tennessee-state",
        "Tennessee St": "tennessee-state",
        "Tenn. Martin": "tennessee-martin",
        "Tennessee Martin": "tennessee-martin",
        "UT Martin": "tennessee-martin",
        "Jacksonville St": "jacksonville-state",
        "Jacksonville St.": "jacksonville-state",
        "Kennesaw St": "kennesaw-state",
        "Kennesaw St.": "kennesaw-state",
        "N Alabama": "north-alabama",
        "North Alabama": "north-alabama",
        "N Florida": "north-florida",
        "North Florida": "north-florida",
        "Central Ark.": "central-arkansas",
        "Central Arkansas": "central-arkansas",
        "Coastal Carolina": "coastal-carolina",
        "Coastal Car.": "coastal-carolina",
        "Ga. Southern": "georgia-southern",
        "Georgia Southern": "georgia-southern",
        "Ga. State": "georgia-state",
        "Georgia State": "georgia-state",
        "TX Southern": "texas-southern",
        "Texas Southern": "texas-southern",
        "Grambling St": "grambling-state",
        "Grambling St.": "grambling-state",
        "Grambling": "grambling-state",
        "Southern U.": "southern",
        "Southern Univ.": "southern",
        "Jackson St": "jackson-state",
        "Jackson St.": "jackson-state",
        "Alcorn St": "alcorn-state",
        "Alcorn St.": "alcorn-state",
        "Alabama A&M": "alabama-am",
        "Alabama St": "alabama-state",
        "Alabama St.": "alabama-state",
        "Miss Valley St": "mississippi-valley-state",
        "Miss. Valley St.": "mississippi-valley-state",
        "MVSU": "mississippi-valley-state",
        "Bethune-Cookman": "bethune-cookman",
        "B-Cookman": "bethune-cookman",
        "Coppin St": "coppin-state",
        "Coppin St.": "coppin-state",
        "Delaware St": "delaware-state",
        "Delaware St.": "delaware-state",
        "Howard": "howard",
        "Morgan St": "morgan-state",
        "Morgan St.": "morgan-state",
        "Norfolk St": "norfolk-state",
        "Norfolk St.": "norfolk-state",
        "SC State": "south-carolina-state",
        "S Carolina St": "south-carolina-state",
        "NC A&T": "north-carolina-at",
        "North Carolina A&T": "north-carolina-at",
        "NC Central": "north-carolina-central",
        "North Carolina Central": "north-carolina-central",
        "Mt. St. Mary's": "mount-st-marys",
        "Mount St. Mary's": "mount-st-marys",
        "Robert Morris": "robert-morris",
        "Sacred Heart": "sacred-heart",
        "Wagner": "wagner",
        "LIU": "long-island-university",
        "Long Island": "long-island-university",
        "Stony Brook": "stony-brook",
        "Albany": "albany",
        "NJIT": "njit",
        "Fairleigh Dickinson": "fairleigh-dickinson",
        "FDU": "fairleigh-dickinson",
        "American": "american",
        "American U.": "american",
        "Boston U.": "boston-university",
        "Boston University": "boston-university",
        "Holy Cross": "holy-cross",
        "Colgate": "colgate",
        "Bucknell": "bucknell",
        "Army": "army",
        "Navy": "navy",
        "Lafayette": "lafayette",
        "Lehigh": "lehigh",
        "Loyola (Md)": "loyola-maryland",
        "Marist": "marist",
        "Rider": "rider",
        "Siena": "siena",
        "Iona": "iona",
        "Monmouth": "monmouth",
        "Quinnipiac": "quinnipiac",
        "Manhattan": "manhattan",
        "Canisius": "canisius",
        "Niagara": "niagara",
        "Fairfield": "fairfield",
        "Hofstra": "hofstra",
        "Northeastern": "northeastern",
        "Drexel": "drexel",
        "Towson": "towson",
        "William & Mary": "william-mary",
        "Wm & Mary": "william-mary",
        "Coll. of William & Mary": "william-mary",
        "James Madison": "james-madison",
        "JMU": "james-madison",
        "Elon": "elon",
        "UNC Wilmington": "unc-wilmington",
        "UNCW": "unc-wilmington",
        "UNC Greensboro": "unc-greensboro",
        "UNCG": "unc-greensboro",
        "Charleston So.": "charleston-southern",
        "Charleston Southern": "charleston-southern",
        "High Point": "high-point",
        "Campbell": "campbell",
        "Gardner-Webb": "gardner-webb",
        "Winthrop": "winthrop",
        "Radford": "radford",
        "Presbyterian": "presbyterian",
        "Longwood": "longwood",
        "Hampton": "hampton",
        "Wofford": "wofford",
        "Chattanooga": "chattanooga",
        "Furman": "furman",
        "Samford": "samford",
        "Mercer": "mercer",
        "ETSU": "east-tennessee-state",
        "E Tenn. St": "east-tennessee-state",
        "E Tennessee St": "east-tennessee-state",
        "East Tennessee St": "east-tennessee-state",
        "VMI": "vmi",
        "Citadel": "citadel",
        "The Citadel": "citadel",
        "UNCG": "unc-greensboro",
        "Western Caro.": "western-carolina",
        "Western Carolina": "western-carolina",
        "Green Bay": "green-bay",
        "Milwaukee": "milwaukee",
        "UWM": "milwaukee",
        "UW-Milwaukee": "milwaukee",
        "Detroit Mercy": "detroit-mercy",
        "Detroit": "detroit-mercy",
        "Oakland": "oakland",
        "Wright St": "wright-state",
        "Wright St.": "wright-state",
        "Youngstown St": "youngstown-state",
        "Youngstown St.": "youngstown-state",
        "Cleveland St": "cleveland-state",
        "Cleveland St.": "cleveland-state",
        "IUPUI": "iupui",
        "Ind.-Purdue": "iupui",
        "Purdue Fort Wayne": "purdue-fort-wayne",
        "PFW": "purdue-fort-wayne",
        "N Dakota St": "north-dakota-state",
        "North Dakota St": "north-dakota-state",
        "North Dakota St.": "north-dakota-state",
        "S Dakota St": "south-dakota-state",
        "South Dakota St": "south-dakota-state",
        "South Dakota St.": "south-dakota-state",
        "N Dakota": "north-dakota",
        "North Dakota": "north-dakota",
        "S Dakota": "south-dakota",
        "South Dakota": "south-dakota",
        "Oral Roberts": "oral-roberts",
        "W Illinois": "western-illinois",
        "Western Illinois": "western-illinois",
        "Denver": "denver",
        "Omaha": "nebraska-omaha",
        "Nebraska Omaha": "nebraska-omaha",
        "St. Thomas": "st-thomas",
        "St Thomas": "st-thomas",
        "Tarleton St": "tarleton-state",
        "Tarleton St.": "tarleton-state",
        "Tarleton": "tarleton-state",
        "Seattle": "seattle",
        "Seattle U": "seattle",
        "Grand Canyon": "grand-canyon",
        "GCU": "grand-canyon",
        "Utah Valley": "utah-valley",
        "UVU": "utah-valley",
        "Cal Baptist": "california-baptist",
        "California Baptist": "california-baptist",
        "CBU": "california-baptist",
        "Dixie St": "dixie-state",
        "Dixie St.": "dixie-state",
        "Dixie State": "dixie-state",
        "Utah Tech": "utah-tech",
        "Southern Utah": "southern-utah",
        "Weber St": "weber-state",
        "Weber St.": "weber-state",
        "Idaho St": "idaho-state",
        "Idaho St.": "idaho-state",
        "Montana St": "montana-state",
        "Montana St.": "montana-state",
        "Portland St": "portland-state",
        "Portland St.": "portland-state",
        "E Washington": "eastern-washington",
        "Eastern Washington": "eastern-washington",
        "N Arizona": "northern-arizona",
        "Northern Arizona": "northern-arizona",
        "N Colorado": "northern-colorado",
        "Northern Colorado": "northern-colorado",
        "Bellarmine": "bellarmine",
        "Jacksonville": "jacksonville",
        "Lipscomb": "lipscomb",
        "Queens": "queens",
        "Stetson": "stetson",
        "Lindenwood": "lindenwood",
        "Le Moyne": "le-moyne",
        "Stonehill": "stonehill",
        "Texas A&M Com.": "texas-am-commerce",
        "Texas A&M Commerce": "texas-am-commerce",
    }

    # Check direct mapping first
    if name in name_map:
        return name_map[name]

    # Basic normalization
    result = name.lower()
    result = result.replace("'", "")
    result = result.replace(".", "")
    result = result.replace("&", "and")
    result = result.replace(" ", "-")
    result = result.replace("state", "-state").replace("--", "-")
    result = result.strip("-")

    return result


def get_team_id(team_name: str) -> Optional[str]:
    """Get team ID from our database by matching normalized name."""
    normalized = normalize_team_name(team_name)
    if not normalized:
        return None

    # Try exact match
    result = supabase.table("teams").select("id").eq("normalized_name", normalized).execute()
    if result.data:
        return result.data[0]["id"]

    # Try partial match on the first word
    first_word = normalized.split("-")[0]
    if first_word and len(first_word) > 3:
        result = supabase.table("teams").select("id, normalized_name").ilike(
            "normalized_name", f"{first_word}%"
        ).execute()
        if result.data and len(result.data) == 1:
            return result.data[0]["id"]

    # Try partial match anywhere
    result = supabase.table("teams").select("id, normalized_name").ilike(
        "normalized_name", f"%{normalized}%"
    ).execute()
    if result.data and len(result.data) == 1:
        return result.data[0]["id"]

    # Try without state suffix
    if "-state" in normalized:
        base_name = normalized.replace("-state", "")
        result = supabase.table("teams").select("id").ilike(
            "normalized_name", f"%{base_name}%"
        ).execute()
        if result.data and len(result.data) == 1:
            return result.data[0]["id"]

    return None


def _fetch_haslametrics_ratings_uncached(season: int = 2025) -> Optional[list]:
    """
    Internal function to fetch Haslametrics ratings without caching.

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)

    Returns:
        List of team rating dicts or None if failed
    """
    # Convert 2025 -> 25 for URL
    season_short = str(season)[-2:]
    url = HASLAMETRICS_BASE_URL.format(season=season_short)

    print(f"Fetching Haslametrics data from: {url}")

    # Use proper headers to avoid being blocked
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # Note: brotli package must be installed for automatic Brotli decompression
        # Haslametrics serves Content-Encoding: br (Brotli compressed)
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse XML (requests auto-decompresses Brotli when brotli package is installed)
        root = ET.fromstring(response.content)
        teams = []

        for mr in root.findall(".//mr"):
            team_data = {
                "rank": mr.get("rk"),
                "team": mr.get("t"),
                "conference": mr.get("c"),
                "wins": mr.get("w"),
                "losses": mr.get("l"),
                # Efficiency metrics (ou/du are offensive/defensive units)
                "offensive_efficiency": mr.get("ou"),
                "defensive_efficiency": mr.get("du"),
                # Shooting percentages
                "ft_pct": mr.get("ftpct"),
                "dft_pct": mr.get("dftpct"),  # Defensive FT% allowed
                # Momentum metrics
                "momentum_overall": mr.get("mom"),
                "momentum_offense": mr.get("mmo"),  # Correct attribute name
                "momentum_defense": mr.get("mmd"),  # Correct attribute name
                # Quality metrics
                "consistency": mr.get("inc"),  # Inconsistency metric (lower = more consistent)
                "sos": mr.get("sos"),
                "rpi": mr.get("rpi"),
                "all_play_pct": mr.get("ap"),  # All-Play Percentage (core metric)
                "win_rate": mr.get("wr"),
                # Recent performance
                "last_5_record": mr.get("p5wl"),
                "last_5_trend": mr.get("p5ud"),  # Up/down trend
                # Quadrant records (NET-based)
                "quad_1_record": mr.get("r_q1"),
                "quad_2_record": mr.get("r_q2"),
                "quad_3_record": mr.get("r_q3"),
                "quad_4_record": mr.get("r_q4"),
                # Home/Away/Neutral records
                "home_record": mr.get("r_home"),
                "away_record": mr.get("r_away"),
                "neutral_record": mr.get("r_neut"),
            }
            teams.append(team_data)

        print(f"Fetched {len(teams)} team ratings from Haslametrics")
        return teams

    except requests.exceptions.RequestException as e:
        print(f"HTTP error fetching Haslametrics data: {e}")
        return None
    except ET.ParseError as e:
        print(f"XML parsing error: {e}")
        return None
    except Exception as e:
        print(f"Error fetching Haslametrics data: {e}")
        return None


def fetch_haslametrics_ratings(season: int = 2025, use_cache: bool = True) -> Optional[list]:
    """
    Fetch Haslametrics ratings from their XML endpoint with caching.

    Caches results for 1 hour to reduce external API calls.

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)
        use_cache: Whether to use cached data (default: True)

    Returns:
        List of team rating dicts or None if failed
    """
    cache_key_kwargs = {"season": season}

    # Try cache first if enabled
    if use_cache:
        cached_data = ratings_cache.get("haslametrics_ratings", **cache_key_kwargs)
        if cached_data is not None:
            logger.info(f"Cache HIT: haslametrics_ratings (season={season})")
            print(f"Using cached Haslametrics ratings for {season}")
            return cached_data

    logger.info(f"Cache MISS: haslametrics_ratings (season={season})")

    # Fetch fresh data
    ratings = _fetch_haslametrics_ratings_uncached(season)

    # Cache the result if successful
    if ratings is not None and len(ratings) > 0:
        ratings_cache.set("haslametrics_ratings", ratings, **cache_key_kwargs)
        logger.info(f"Cache SET: haslametrics_ratings (season={season}, {len(ratings)} teams)")

    return ratings


def store_haslametrics_ratings(teams: list, season: int) -> dict:
    """
    Store Haslametrics ratings in Supabase.

    Args:
        teams: List of team rating dicts from XML
        season: Season year

    Returns:
        Dict with counts of inserted/skipped/errors
    """
    print(f"\n=== Storing Haslametrics Ratings ===")

    inserted = 0
    skipped = 0
    errors = 0
    unmatched_teams = []

    for team_data in teams:
        try:
            team_name = team_data.get("team", "")
            team_id = get_team_id(team_name)

            if not team_id:
                skipped += 1
                unmatched_teams.append(team_name)
                continue

            # Calculate efficiency margin
            oe = safe_float(team_data.get("offensive_efficiency"))
            de = safe_float(team_data.get("defensive_efficiency"))
            efficiency_margin = None
            if oe is not None and de is not None:
                efficiency_margin = round(oe - de, 2)

            rating_data = {
                "team_id": team_id,
                "season": season,
                "captured_date": datetime.now().date().isoformat(),
                "rank": safe_int(team_data.get("rank")),
                "offensive_efficiency": oe,
                "defensive_efficiency": de,
                "efficiency_margin": efficiency_margin,
                "ft_pct": safe_float(team_data.get("ft_pct")),
                "momentum_overall": safe_float(team_data.get("momentum_overall")),
                "momentum_offense": safe_float(team_data.get("momentum_offense")),
                "momentum_defense": safe_float(team_data.get("momentum_defense")),
                "consistency": safe_float(team_data.get("consistency")),
                "sos": safe_float(team_data.get("sos")),
                "rpi": safe_float(team_data.get("rpi")),
                "all_play_pct": safe_float(team_data.get("all_play_pct")),
                "last_5_record": team_data.get("last_5_record"),
                "quad_1_record": team_data.get("quad_1_record"),
                "quad_2_record": team_data.get("quad_2_record"),
                "quad_3_record": team_data.get("quad_3_record"),
                "quad_4_record": team_data.get("quad_4_record"),
                "wins": safe_int(team_data.get("wins")),
                "losses": safe_int(team_data.get("losses")),
                "conference": team_data.get("conference"),
            }

            # Remove None values
            rating_data = {k: v for k, v in rating_data.items() if v is not None}

            # Insert into Supabase
            supabase.table("haslametrics_ratings").insert(rating_data).execute()
            inserted += 1

            if inserted % 50 == 0:
                print(f"  Inserted {inserted} ratings...")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error storing {team_name}: {e}")

    print(f"Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")

    # Show sample of unmatched teams for debugging
    if unmatched_teams and len(unmatched_teams) <= 20:
        print(f"  Unmatched teams: {unmatched_teams[:20]}")
    elif unmatched_teams:
        print(f"  Sample unmatched: {unmatched_teams[:10]}... (+{len(unmatched_teams)-10} more)")

    return {"inserted": inserted, "skipped": skipped, "errors": errors}


def safe_int(value) -> Optional[int]:
    """Safely convert to int."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return int(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


def safe_float(value) -> Optional[float]:
    """Safely convert to float."""
    if value is None or value == "" or value == "N/A":
        return None
    try:
        return float(str(value).replace(",", "").replace("%", ""))
    except (ValueError, TypeError):
        return None


def get_team_haslametrics_rating(team_id: str, season: int = 2025, use_cache: bool = True) -> Optional[dict]:
    """
    Get the latest Haslametrics rating for a team with caching.

    Caches individual team ratings for 1 hour.

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
    result = supabase.table("haslametrics_ratings").select("*").eq(
        "team_id", team_id
    ).eq("season", season).order("captured_at", desc=True).limit(1).execute()

    if result.data:
        # Cache the result
        ratings_cache.set("haslametrics_team", result.data[0], **cache_key_kwargs)
        logger.debug(f"Cache SET: haslametrics_team (team_id={team_id[:8]}..., season={season})")
        return result.data[0]

    return None


def invalidate_haslametrics_cache() -> dict:
    """
    Invalidate all Haslametrics-related caches.

    Call this before fetching fresh data to ensure no stale data is served.

    Returns:
        Dict with counts of invalidated entries
    """
    ratings_count = ratings_cache.invalidate("haslametrics_ratings")
    team_count = ratings_cache.invalidate("haslametrics_team")

    logger.info(f"Haslametrics cache invalidated: ratings={ratings_count}, teams={team_count}")

    return {
        "ratings_invalidated": ratings_count,
        "teams_invalidated": team_count,
    }


def refresh_haslametrics_data(season: int = 2025) -> dict:
    """
    Full refresh of Haslametrics data.

    Invalidates cache before fetching fresh data.

    Args:
        season: Season year to fetch

    Returns:
        Results dict
    """
    print("=" * 60)
    print("Haslametrics Data Refresh (FREE)")
    print(f"Season: {season}")
    print(f"Started at: {datetime.now().isoformat()}")
    print("=" * 60)

    results = {
        "timestamp": datetime.now().isoformat(),
        "season": season,
        "status": "success",
    }

    # Invalidate cache before refresh
    cache_results = invalidate_haslametrics_cache()
    results["cache_invalidated"] = cache_results
    print(f"Cache invalidated: {cache_results}")

    # Fetch ratings (bypass cache since we just invalidated)
    teams = fetch_haslametrics_ratings(season, use_cache=False)

    if teams is None or len(teams) == 0:
        results["status"] = "error"
        results["error"] = "Failed to fetch Haslametrics data"
        return results

    # Store in database
    store_results = store_haslametrics_ratings(teams, season)
    results["ratings"] = store_results

    print("\n" + "=" * 60)
    print("Haslametrics Refresh Complete")
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

    results = refresh_haslametrics_data(season)
    print("\nResults:")
    print(json.dumps(results, indent=2))

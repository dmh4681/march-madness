"""
Haslametrics Data Scraper

Fetches advanced analytics from Haslametrics.
FREE - No subscription required!

Haslametrics Overview:
======================
Haslametrics (haslametrics.com) is a free alternative to KenPom that uses a
unique "All-Play Percentage" methodology. Created by T.J. Haslett.

Key Differences from KenPom:
- All-Play % is the core metric (vs KenPom's AdjEM)
- Momentum metrics show recent trend direction
- FREE (vs KenPom's $20/year subscription)
- XML data feed (vs KenPom's HTML scraping)

Key Metrics Collected:
=====================
- All-Play Percentage (ap): Probability of beating an average D1 team on a
  neutral court. Top teams: 95%+, Bottom teams: <10%
- Offensive Efficiency (ou): Points per 100 possessions
- Defensive Efficiency (du): Points allowed per 100 possessions
- Momentum Overall (mom): Recent performance trend (-1 to +1 scale)
- Momentum Offense (mmo): Offensive trend
- Momentum Defense (mmd): Defensive trend
- Consistency (inc): Inconsistency metric (lower = more consistent)
- Quadrant Records: Performance vs NET quadrants (Q1 = best opponents)
- Last 5 Record: Recent 5-game performance

How These Are Used in AI Analysis:
==================================
1. All-Play % provides baseline win probability estimate
2. Momentum metrics identify teams trending up/down (value opportunity)
3. Quadrant records show quality of wins (important for tournament)
4. Last 5 indicates current form vs season-long metrics
5. Cross-validation with KenPom when both available

Technical Implementation:
========================
- Data served as XML at haslametrics.com/ratings{YY}.xml
- Server uses Brotli compression (Content-Encoding: br)
- Requires 'brotli' Python package for decompression
- User-Agent header required (server blocks naked requests)

Usage:
    python -m backend.data_collection.haslametrics_scraper
    python -m backend.data_collection.haslametrics_scraper 2025

No environment variables required (it's FREE!).
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

    Haslametrics uses heavily abbreviated team names to fit their XML format.
    This function maps those abbreviations to our normalized format.

    Common Haslametrics Abbreviations:
    - "N Carolina" -> "north-carolina"
    - "S Florida" -> "south-florida"
    - "Abil. Christian" -> "abilene-christian"
    - "St." and "St" for "Saint"
    - "St." for "State"

    The name_map below is extensive because Haslametrics uses unique
    abbreviations not seen in other sources. If you see unmatched teams
    in the logs, add the mapping here.

    Args:
        name: Team name as it appears in Haslametrics XML

    Returns:
        Normalized team name matching our teams.normalized_name column
    """
    if not name:
        return ""

    # Extensive mappings for Haslametrics' abbreviated naming conventions
    # Keys: Haslametrics XML names, Values: Our normalized_name format
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
    Internal function to fetch Haslametrics ratings from their XML endpoint.

    Technical Implementation:
    ========================
    Haslametrics serves team ratings as an XML file with a predictable URL pattern:
    - URL: https://haslametrics.com/ratings{YY}.xml (e.g., ratings25.xml for 2024-25)

    The server requires proper headers or it will block the request:
    - User-Agent: Must look like a real browser
    - Accept: Should include application/xml

    Response Handling:
    - Server uses Brotli compression (Content-Encoding: br)
    - The 'brotli' Python package must be installed for auto-decompression
    - Response is XML with <mr> elements for each team

    XML Attribute Reference (from Haslametrics):
    ============================================
    Each <mr> element contains these attributes:
    - rk: Overall rank (1-362)
    - t: Team name (abbreviated)
    - c: Conference abbreviation
    - w/l: Wins/Losses
    - ou: Offensive efficiency (points per 100 possessions)
    - du: Defensive efficiency (points allowed per 100 possessions)
    - ap: All-Play Percentage (core metric: win probability vs avg D1 team)
    - mom: Momentum overall (recent trend, -1 to +1)
    - mmo: Momentum offense
    - mmd: Momentum defense
    - inc: Inconsistency (lower = more consistent)
    - sos: Strength of schedule
    - p5wl: Last 5 games record (e.g., "4-1")
    - r_q1 through r_q4: Quadrant records (vs NET quadrants)

    Args:
        season: The season year (e.g., 2025 for 2024-25 season)

    Returns:
        List of team rating dicts or None if fetch/parse failed

    Note: If you see "brotli" or decompression errors, install with:
        pip install brotli
    """
    # Convert 4-digit year to 2-digit for URL (2025 -> "25")
    season_short = str(season)[-2:]
    url = HASLAMETRICS_BASE_URL.format(season=season_short)

    print(f"Fetching Haslametrics data from: {url}")

    # Headers required to avoid being blocked by Haslametrics server
    # The server checks User-Agent and rejects requests without browser-like headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/xml, text/xml, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        # IMPORTANT: The 'brotli' package must be installed for this to work!
        # Haslametrics uses Brotli compression (Content-Encoding: br)
        # requests library auto-decompresses when brotli package is installed
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        # Parse XML response into ElementTree
        # The root element contains <mr> (metrics row) elements for each team
        root = ET.fromstring(response.content)
        teams = []

        # Iterate through all <mr> elements in the XML
        # Each <mr> contains one team's full metrics as XML attributes
        for mr in root.findall(".//mr"):
            # Extract all metrics from XML attributes
            # Attribute names are abbreviated to minimize XML size
            team_data = {
                # Core identification
                "rank": mr.get("rk"),           # Overall Haslametrics rank
                "team": mr.get("t"),            # Team name (abbreviated)
                "conference": mr.get("c"),      # Conference abbreviation
                "wins": mr.get("w"),            # Season wins
                "losses": mr.get("l"),          # Season losses

                # Efficiency metrics (core stats for analysis)
                # ou/du = Offensive/Defensive Units (points per 100 possessions)
                "offensive_efficiency": mr.get("ou"),
                "defensive_efficiency": mr.get("du"),

                # Shooting percentages (less commonly used)
                "ft_pct": mr.get("ftpct"),      # Free throw percentage
                "dft_pct": mr.get("dftpct"),    # Opponent FT% allowed

                # Momentum metrics - KEY FOR IDENTIFYING TRENDING TEAMS
                # Positive = improving, Negative = declining
                "momentum_overall": mr.get("mom"),   # Combined momentum
                "momentum_offense": mr.get("mmo"),   # Offensive trend
                "momentum_defense": mr.get("mmd"),   # Defensive trend

                # Quality/consistency metrics
                "consistency": mr.get("inc"),   # Inconsistency (lower = better)
                "sos": mr.get("sos"),           # Strength of schedule
                "rpi": mr.get("rpi"),           # RPI rating
                "all_play_pct": mr.get("ap"),   # All-Play % (CORE METRIC)
                "win_rate": mr.get("wr"),       # Actual win rate

                # Recent performance - VALUABLE FOR CURRENT FORM
                "last_5_record": mr.get("p5wl"),    # Last 5 games (e.g., "4-1")
                "last_5_trend": mr.get("p5ud"),    # Trend direction

                # Quadrant records - CRITICAL FOR TOURNAMENT EVALUATION
                # Q1 = best opponents (NET 1-30 home, 1-50 neutral, 1-75 road)
                "quad_1_record": mr.get("r_q1"),
                "quad_2_record": mr.get("r_q2"),
                "quad_3_record": mr.get("r_q3"),
                "quad_4_record": mr.get("r_q4"),

                # Home/Away/Neutral splits
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
    Store Haslametrics ratings in Supabase database.

    Data Transformation Process:
    ===========================
    1. Match each Haslametrics team name to our teams table
    2. Calculate derived metrics (efficiency_margin = offense - defense)
    3. Convert string values to proper numeric types
    4. Insert into haslametrics_ratings table

    Database Schema (haslametrics_ratings table):
    ============================================
    - team_id: FK to teams.id
    - season: Year (e.g., 2025)
    - captured_date: Date when data was fetched
    - rank: Overall Haslametrics ranking
    - offensive_efficiency/defensive_efficiency: Points per 100 possessions
    - efficiency_margin: Calculated OE - DE
    - all_play_pct: Core metric (0-100, probability of beating avg D1 team)
    - momentum_overall/offense/defense: Recent trends (-1 to +1)
    - consistency: Inconsistency metric (lower = more reliable)
    - sos: Strength of schedule
    - quad_1_record through quad_4_record: Performance vs NET quadrants
    - last_5_record: Recent 5-game performance string

    Team Matching:
    =============
    Haslametrics uses heavily abbreviated team names. If many teams fail to
    match, add mappings to normalize_team_name(). The unmatched teams are
    logged at the end for debugging.

    Args:
        teams: List of team rating dicts from XML parsing
        season: Season year

    Returns:
        Dict with counts: {inserted, skipped, errors}
    """
    print(f"\n=== Storing Haslametrics Ratings ===")

    inserted = 0
    skipped = 0
    errors = 0
    unmatched_teams = []  # Track unmatched for debugging

    for team_data in teams:
        try:
            team_name = team_data.get("team", "")
            team_id = get_team_id(team_name)

            if not team_id:
                skipped += 1
                unmatched_teams.append(team_name)
                continue

            # Calculate efficiency margin (similar to KenPom's AdjEM)
            # This derived metric is useful for cross-validation with KenPom
            oe = safe_float(team_data.get("offensive_efficiency"))
            de = safe_float(team_data.get("defensive_efficiency"))
            efficiency_margin = None
            if oe is not None and de is not None:
                efficiency_margin = round(oe - de, 2)

            # Build rating data dict for database insert
            rating_data = {
                # Core identification
                "team_id": team_id,
                "season": season,
                "captured_date": datetime.now().date().isoformat(),

                # Rankings
                "rank": safe_int(team_data.get("rank")),

                # Efficiency metrics (points per 100 possessions)
                "offensive_efficiency": oe,
                "defensive_efficiency": de,
                "efficiency_margin": efficiency_margin,  # Calculated: OE - DE

                # All-Play Percentage: THE CORE HASLAMETRICS METRIC
                # Represents probability of beating an average D1 team
                # on a neutral court. Top 10 teams typically 90%+
                "all_play_pct": safe_float(team_data.get("all_play_pct")),

                # Free throw percentage
                "ft_pct": safe_float(team_data.get("ft_pct")),

                # Momentum metrics: KEY FOR FINDING TRENDING TEAMS
                # Scale: typically -0.5 to +0.5
                # Positive = team improving, Negative = team declining
                "momentum_overall": safe_float(team_data.get("momentum_overall")),
                "momentum_offense": safe_float(team_data.get("momentum_offense")),
                "momentum_defense": safe_float(team_data.get("momentum_defense")),

                # Consistency: lower values = more consistent/predictable team
                "consistency": safe_float(team_data.get("consistency")),

                # Strength metrics
                "sos": safe_float(team_data.get("sos")),
                "rpi": safe_float(team_data.get("rpi")),

                # Recent form: string like "4-1" for last 5 games
                # Critical for identifying current form vs season averages
                "last_5_record": team_data.get("last_5_record"),

                # Quadrant records: CRITICAL FOR TOURNAMENT EVALUATION
                # Q1 = best opponents, Q4 = weakest
                # Strong Q1 records indicate true quality
                # Q3/Q4 losses are red flags
                "quad_1_record": team_data.get("quad_1_record"),
                "quad_2_record": team_data.get("quad_2_record"),
                "quad_3_record": team_data.get("quad_3_record"),
                "quad_4_record": team_data.get("quad_4_record"),

                # Season record
                "wins": safe_int(team_data.get("wins")),
                "losses": safe_int(team_data.get("losses")),
                "conference": team_data.get("conference"),
            }

            # Remove None values before insert
            rating_data = {k: v for k, v in rating_data.items() if v is not None}

            # Insert into Supabase (not upsert - we want daily snapshots for historical analysis)
            supabase.table("haslametrics_ratings").insert(rating_data).execute()
            inserted += 1

            # Progress indicator
            if inserted % 50 == 0:
                print(f"  Inserted {inserted} ratings...")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error storing {team_name}: {e}")

    print(f"Inserted: {inserted}, Skipped: {skipped}, Errors: {errors}")

    # Debug output: show unmatched teams so we can add mappings
    # If you see familiar team names here, add them to normalize_team_name()
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

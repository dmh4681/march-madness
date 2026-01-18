"""
AP Poll Rankings Fetcher

Scrapes historical AP Poll data from College Poll Archive.
Maps rankings to specific game dates.

Usage:
    python rankings.py --season 2024
    python rankings.py --seasons 2014-2024
"""

import argparse
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from schema import get_connection, init_database


BASE_URL = "https://www.collegepollarchive.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Cache for rankings by week
_rankings_cache = {}


def fetch_season_polls(season: int, delay: float = 2.0) -> list[dict]:
    """
    Fetch all AP Poll weeks for a season from College Poll Archive.

    Args:
        season: Season year (e.g., 2024 for 2023-24 season)
        delay: Seconds between requests

    Returns:
        List of poll week dicts with rankings
    """
    all_polls = []

    # Season page URL
    # College Poll Archive uses the end year (2024 for 2023-24)
    url = f"{BASE_URL}/basketball/men/ap/seasons/byYear-{season}.cfm"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")

        # Find links to individual poll weeks
        poll_links = soup.find_all("a", href=re.compile(r"/ap/seasons/\d+-Week"))

        print(f"Season {season}: Found {len(poll_links)} poll weeks")

        for link in poll_links:
            week_url = BASE_URL + link["href"]
            week_text = link.text.strip()

            # Extract week number from text (e.g., "Week 1" -> 1)
            week_match = re.search(r"Week\s+(\d+)", week_text)
            if not week_match:
                continue

            week_num = int(week_match.group(1))

            try:
                poll_data = fetch_poll_week(week_url, season, week_num)
                if poll_data:
                    all_polls.extend(poll_data)
                    print(f"  Week {week_num}: {len(poll_data)} teams")

                time.sleep(delay)

            except Exception as e:
                print(f"  Week {week_num}: Error - {e}")
                time.sleep(delay * 2)

    except Exception as e:
        print(f"Error fetching season {season}: {e}")

    return all_polls


def fetch_poll_week(url: str, season: int, week: int) -> list[dict]:
    """
    Fetch rankings for a specific poll week.

    Returns list of dicts with team ranking data.
    """
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")

    rankings = []

    # Find the poll table
    table = soup.find("table", class_="table")
    if not table:
        return rankings

    # Try to find poll date from page
    poll_date = None
    date_elem = soup.find(string=re.compile(r"\w+ \d+, \d{4}"))
    if date_elem:
        try:
            poll_date = datetime.strptime(date_elem.strip(), "%B %d, %Y").date()
        except ValueError:
            pass

    # If no date found, estimate based on week number
    if poll_date is None:
        # Season starts around Nov 1
        season_start = datetime(season - 1, 11, 1)
        poll_date = (season_start + timedelta(weeks=week - 1)).date()

    # Parse table rows
    rows = table.find_all("tr")[1:]  # Skip header

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        try:
            rank = int(cells[0].text.strip())
            team = cells[1].text.strip()

            # Clean team name (remove record if present)
            team = re.sub(r"\s*\(\d+-\d+\)\s*", "", team).strip()

            # Try to get votes/points if available
            first_place = None
            total_points = None
            if len(cells) >= 4:
                try:
                    first_place = int(cells[2].text.strip())
                except ValueError:
                    pass
                try:
                    total_points = int(cells[3].text.strip().replace(",", ""))
                except ValueError:
                    pass

            rankings.append(
                {
                    "season": season,
                    "week": week,
                    "poll_date": poll_date,
                    "team": team,
                    "rank": rank,
                    "first_place_votes": first_place,
                    "total_points": total_points,
                }
            )

        except (ValueError, IndexError) as e:
            continue

    return rankings


def save_rankings_to_db(rankings: list[dict]):
    """Save rankings to SQLite database."""
    if not rankings:
        return

    conn = get_connection()
    df = pd.DataFrame(rankings)

    # Insert with replace on conflict
    df.to_sql("ap_rankings", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    print(f"Saved {len(rankings)} ranking entries to database")


def save_rankings_to_csv(rankings: list[dict], filename: str):
    """Save rankings to CSV file."""
    if not rankings:
        return

    output_path = Path(__file__).parent.parent / "data" / "raw" / filename
    df = pd.DataFrame(rankings)
    df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")


def get_team_rank_on_date(team: str, date: datetime, season: int) -> Optional[int]:
    """
    Get a team's AP ranking for a specific date.

    Uses the most recent poll before the game date.

    Returns None if team was unranked.
    """
    # Check cache first
    cache_key = (season, date)
    if cache_key not in _rankings_cache:
        # Load rankings from DB
        conn = get_connection()
        query = """
            SELECT team, rank, poll_date
            FROM ap_rankings
            WHERE season = ?
            AND poll_date <= ?
            ORDER BY poll_date DESC
        """
        df = pd.read_sql_query(query, conn, params=(season, date))
        conn.close()

        if df.empty:
            return None

        # Get most recent poll
        latest_date = df["poll_date"].max()
        latest_poll = df[df["poll_date"] == latest_date]

        _rankings_cache[cache_key] = dict(zip(latest_poll["team"], latest_poll["rank"]))

    rankings = _rankings_cache.get(cache_key, {})

    # Handle team name variations
    team_normalized = normalize_team_name(team)
    for ranked_team, rank in rankings.items():
        if normalize_team_name(ranked_team) == team_normalized:
            return rank

    return None


def normalize_team_name(name: str) -> str:
    """
    Normalize team name for matching.

    Handles common variations like "UConn" vs "Connecticut".
    """
    name = name.lower().strip()

    # Common mappings
    mappings = {
        "uconn": "connecticut",
        "usc": "southern california",
        "lsu": "louisiana state",
        "smu": "southern methodist",
        "tcu": "texas christian",
        "byu": "brigham young",
        "ole miss": "mississippi",
        "pitt": "pittsburgh",
        "miami (fl)": "miami",
        "miami (oh)": "miami ohio",
    }

    return mappings.get(name, name)


def scrape_multiple_seasons(start_year: int, end_year: int):
    """Scrape AP rankings for multiple seasons."""
    init_database()

    all_rankings = []

    for season in range(start_year, end_year + 1):
        print(f"\nScraping season {season}...")
        try:
            rankings = fetch_season_polls(season)
            all_rankings.extend(rankings)

            save_rankings_to_csv(rankings, f"ap_rankings_{season}.csv")
            save_rankings_to_db(rankings)

            time.sleep(5)  # Pause between seasons

        except Exception as e:
            print(f"Failed to scrape season {season}: {e}")
            continue

    # Combined file
    if all_rankings:
        save_rankings_to_csv(all_rankings, f"ap_rankings_{start_year}_{end_year}.csv")
        print(f"\nTotal rankings collected: {len(all_rankings)}")


def main():
    parser = argparse.ArgumentParser(description="Fetch AP Poll rankings")
    parser.add_argument("--season", type=int, help="Single season to fetch")
    parser.add_argument(
        "--seasons", type=str, help="Season range (e.g., 2014-2024)", default="2020-2024"
    )

    args = parser.parse_args()

    if args.season:
        rankings = fetch_season_polls(args.season)
        save_rankings_to_csv(rankings, f"ap_rankings_{args.season}.csv")
        save_rankings_to_db(rankings)
    else:
        start, end = map(int, args.seasons.split("-"))
        scrape_multiple_seasons(start, end)


if __name__ == "__main__":
    main()

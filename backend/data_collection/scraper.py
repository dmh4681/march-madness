"""
NCAA Basketball Game Data Scraper

Uses CBBpy as primary data source for game scores, rankings, and schedules.
Scrapes in 2-week chunks for efficiency.

Usage:
    python scraper.py --years 2020-2024
    python scraper.py --year 2023 --validate
"""

import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

try:
    import cbbpy.mens_scraper as cbb
except ImportError:
    print("CBBpy not installed. Run: pip install cbbpy")
    cbb = None

from schema import get_connection, init_database


# Power conferences for filtering
POWER_CONFERENCES = ["ACC", "Big Ten", "Big 12", "SEC", "Pac-12", "Big East"]


def get_season_date_range(season: int) -> tuple[str, str]:
    """
    Get start and end dates for a college basketball season.
    Season 2024 = 2023-24 season (Nov 2023 - Apr 2024)
    """
    start_date = f"11-01-{season - 1}"
    end_date = f"04-10-{season}"
    return start_date, end_date


def scrape_season_games(season: int, chunk_days: int = 14) -> pd.DataFrame:
    """
    Scrape all games for a given season using CBBpy.
    Uses 2-week chunks for efficiency.

    Args:
        season: Season year (e.g., 2024 for 2023-24 season)
        chunk_days: Days per chunk (default 14 = 2 weeks)

    Returns:
        DataFrame with game data
    """
    if cbb is None:
        raise ImportError("CBBpy required for scraping")

    print(f"\nScraping season {season-1}-{str(season)[2:]}...")

    start_date, end_date = get_season_date_range(season)
    current_date = datetime.strptime(start_date, "%m-%d-%Y")
    end = datetime.strptime(end_date, "%m-%d-%Y")

    all_games = []
    chunk_num = 0

    while current_date < end:
        chunk_end = min(current_date + timedelta(days=chunk_days - 1), end)
        start_str = current_date.strftime("%m-%d-%Y")
        end_str = chunk_end.strftime("%m-%d-%Y")

        chunk_num += 1
        print(f"  Chunk {chunk_num}: {start_str} to {end_str}...", end=" ", flush=True)

        try:
            # CBBpy handles the full range in one call
            # CRITICAL: box=False, pbp=False skips detailed data for 10x speed
            games = cbb.get_games_range(start_str, end_str, info=True, box=False, pbp=False)

            if games is not None and len(games) > 0:
                # Returns tuple (info, boxscore, pbp) - we only need info
                if isinstance(games, tuple):
                    game_info = games[0]  # First element is game info
                else:
                    game_info = games

                for _, game in game_info.iterrows():
                    game_data = extract_game_data(game, season)
                    if game_data:
                        all_games.append(game_data)

                print(f"{len(game_info)} games")
            else:
                print("0 games")

            time.sleep(1)  # Brief pause between chunks

        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)

        current_date = chunk_end + timedelta(days=1)

    df = pd.DataFrame(all_games)
    print(f"Season {season}: {len(df)} total games scraped")
    return df


def extract_game_data(game_row, season: int) -> Optional[dict]:
    """
    Extract relevant fields from CBBpy game row.
    Returns None if data is invalid.
    """
    try:
        # CBBpy column names (may vary by version)
        # Try different possible column names
        game_id = None
        for col in ['game_id', 'id', 'gameId']:
            if col in game_row.index:
                game_id = str(game_row[col])
                break

        if not game_id:
            # Generate ID from date and teams
            game_id = f"{game_row.get('date', 'unknown')}_{hash(str(game_row))}"

        # Team names - try various column formats
        home_team = None
        away_team = None
        for h_col, a_col in [('home_team', 'away_team'), ('home', 'away'),
                            ('homeTeam', 'awayTeam')]:
            if h_col in game_row.index:
                home_team = game_row[h_col]
                away_team = game_row[a_col]
                break

        if not home_team or not away_team:
            return None

        # Scores
        home_score = None
        away_score = None
        for h_col, a_col in [('home_score', 'away_score'), ('homeScore', 'awayScore'),
                            ('home_pts', 'away_pts')]:
            if h_col in game_row.index:
                home_score = game_row[h_col]
                away_score = game_row[a_col]
                break

        # Rankings (CBBpy includes these when available)
        home_rank = None
        away_rank = None
        for h_col, a_col in [('home_rank', 'away_rank'), ('homeRank', 'awayRank')]:
            if h_col in game_row.index:
                home_rank = game_row[h_col]
                away_rank = game_row[a_col]
                break

        # Convert empty/nan to None
        if pd.isna(home_rank) or home_rank == "" or home_rank == 0:
            home_rank = None
        if pd.isna(away_rank) or away_rank == "" or away_rank == 0:
            away_rank = None

        # Conferences
        home_conf = None
        away_conf = None
        for h_col, a_col in [('home_conf', 'away_conf'), ('homeConf', 'awayConf'),
                            ('home_conference', 'away_conference')]:
            if h_col in game_row.index:
                home_conf = game_row[h_col]
                away_conf = game_row[a_col]
                break

        # Derived fields
        same_conference = False
        if home_conf and away_conf:
            same_conference = str(home_conf).strip() == str(away_conf).strip()

        ranked_vs_unranked = (home_rank is not None) != (away_rank is not None)

        # Date
        game_date = game_row.get('date', game_row.get('game_date', None))

        return {
            "game_id": game_id,
            "date": game_date,
            "season": season,
            "home_team": str(home_team),
            "away_team": str(away_team),
            "home_conference": str(home_conf) if home_conf else None,
            "away_conference": str(away_conf) if away_conf else None,
            "home_ap_rank": int(home_rank) if home_rank else None,
            "away_ap_rank": int(away_rank) if away_rank else None,
            "home_score": int(home_score) if pd.notna(home_score) else None,
            "away_score": int(away_score) if pd.notna(away_score) else None,
            "same_conference": same_conference,
            "ranked_vs_unranked": ranked_vs_unranked,
            "source": "cbbpy",
        }

    except Exception as e:
        # Silently skip problematic rows
        return None


def save_games_to_db(df: pd.DataFrame):
    """Save games DataFrame to SQLite database."""
    if df.empty:
        print("No games to save")
        return

    conn = get_connection()

    # Convert boolean to int for SQLite
    df = df.copy()
    df["same_conference"] = df["same_conference"].astype(int)
    df["ranked_vs_unranked"] = df["ranked_vs_unranked"].astype(int)

    # Insert with replace on conflict
    df.to_sql("games", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()
    print(f"Saved {len(df)} games to database")


def save_games_to_csv(df: pd.DataFrame, filename: str):
    """Save games DataFrame to CSV file."""
    if df.empty:
        print("No games to save")
        return

    output_path = Path(__file__).parent.parent / "data" / "raw" / filename
    df.to_csv(output_path, index=False)
    print(f"Saved to {output_path}")


def scrape_multiple_seasons(start_year: int, end_year: int, save_csv: bool = True):
    """
    Scrape multiple seasons of game data.
    """
    init_database()

    all_games = []

    for season in range(start_year, end_year + 1):
        try:
            df = scrape_season_games(season)

            if not df.empty:
                all_games.append(df)

                if save_csv:
                    save_games_to_csv(df, f"games_{season}.csv")

                # Save to DB after each season (in case of crash)
                save_games_to_db(df)

            print(f"Completed season {season}")
            time.sleep(3)  # Pause between seasons

        except Exception as e:
            print(f"Failed to scrape season {season}: {e}")
            import traceback
            traceback.print_exc()
            continue

    # Combine all seasons
    if all_games:
        combined = pd.concat(all_games, ignore_index=True)
        if save_csv:
            save_games_to_csv(combined, f"games_{start_year}_{end_year}.csv")
        print(f"\nTotal games collected: {len(combined)}")
        return combined

    return pd.DataFrame()


def validate_data(df: pd.DataFrame):
    """Print data quality summary."""
    print("\n" + "=" * 60)
    print("DATA VALIDATION SUMMARY")
    print("=" * 60)

    print(f"\nTotal games: {len(df)}")

    if 'date' in df.columns:
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    print(f"\nNull values:")
    print(df.isnull().sum())

    print(f"\nSame-conference games: {df['same_conference'].sum()}")
    print(f"Ranked vs unranked: {df['ranked_vs_unranked'].sum()}")

    # Target dataset
    target = df[(df["same_conference"] == True) & (df["ranked_vs_unranked"] == True)]
    print(f"\nTARGET DATASET (same conf + ranked vs unranked): {len(target)}")
    print("Need >500 games for statistical significance")


def main():
    parser = argparse.ArgumentParser(description="Scrape NCAA basketball game data")
    parser.add_argument(
        "--years", type=str, help="Year range (e.g., 2020-2024)", default="2020-2024"
    )
    parser.add_argument("--year", type=int, help="Single year to scrape")
    parser.add_argument(
        "--validate", action="store_true", help="Run validation on existing data"
    )

    args = parser.parse_args()

    if args.validate:
        # Load existing data and validate
        data_path = Path(__file__).parent.parent / "data" / "raw"
        csv_files = list(data_path.glob("games_*.csv"))
        if csv_files:
            df = pd.concat([pd.read_csv(f) for f in csv_files])
            validate_data(df)
        else:
            print("No data files found. Run scraper first.")
        return

    if args.year:
        df = scrape_season_games(args.year)
        if not df.empty:
            save_games_to_csv(df, f"games_{args.year}.csv")
            save_games_to_db(df)
            validate_data(df)
    else:
        start, end = map(int, args.years.split("-"))
        df = scrape_multiple_seasons(start, end)
        if not df.empty:
            validate_data(df)


if __name__ == "__main__":
    main()

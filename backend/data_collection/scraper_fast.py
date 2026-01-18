"""
Fast NCAA Basketball Game Data Scraper

Uses team schedules instead of game-by-game scraping.
MUCH faster: ~1 minute per season vs hours.

Usage:
    python scraper_fast.py --years 2020-2024
"""

import argparse
import time
from pathlib import Path
from typing import Optional
import re

import pandas as pd

try:
    import cbbpy.mens_scraper as cbb
except ImportError:
    print("CBBpy not installed. Run: pip install cbbpy")
    cbb = None

from schema import get_connection, init_database


# Major conferences to scrape
CONFERENCES = ['acc', 'big-ten', 'big-12', 'sec', 'big-east', 'pac-12']

# Conference display names
CONF_NAMES = {
    'acc': 'ACC',
    'big-ten': 'Big Ten',
    'big-12': 'Big 12',
    'sec': 'SEC',
    'big-east': 'Big East',
    'pac-12': 'Pac-12',
}


def get_conference_teams(conference: str, season: int) -> list[str]:
    """Get list of teams in a conference for a season."""
    try:
        teams = cbb.get_teams_from_conference(conference, season)
        return [str(t).lower().replace(' ', '-') for t in teams]
    except Exception as e:
        print(f"Error getting teams for {conference}: {e}")
        return []


def scrape_team_schedule(team: str, season: int, conference: str) -> list[dict]:
    """Scrape a team's schedule and extract game data."""
    games = []

    try:
        schedule = cbb.get_team_schedule(team, season)

        if schedule is None or schedule.empty:
            return games

        for _, row in schedule.iterrows():
            game_data = extract_schedule_game(row, team, season, conference)
            if game_data:
                games.append(game_data)

    except Exception as e:
        # Silently skip errors for individual teams
        pass

    return games


def extract_schedule_game(row, team: str, season: int, team_conf: str) -> Optional[dict]:
    """Extract game data from schedule row."""
    try:
        game_id = str(row.get('game_id', ''))
        if not game_id:
            return None

        opponent = str(row.get('opponent', ''))
        if not opponent:
            return None

        # Parse game result (e.g., "W 92-54" or "L 73-78")
        result = str(row.get('game_result', ''))
        if not result or result == 'nan':
            return None

        # Parse score
        match = re.match(r'([WL])\s+(\d+)-(\d+)', result)
        if not match:
            return None

        win_loss, score1, score2 = match.groups()
        score1, score2 = int(score1), int(score2)

        # Determine home/away
        # If opponent starts with "@", team was away
        is_away = opponent.startswith('@')
        opponent = opponent.lstrip('@').strip()

        if is_away:
            home_team = opponent
            away_team = team
            if win_loss == 'W':
                home_score, away_score = score2, score1
            else:
                home_score, away_score = score1, score2
        else:
            home_team = team
            away_team = opponent
            if win_loss == 'W':
                home_score, away_score = score1, score2
            else:
                home_score, away_score = score2, score1

        game_date = row.get('game_day', None)

        return {
            "game_id": game_id,
            "date": game_date,
            "season": season,
            "home_team": home_team,
            "away_team": away_team,
            "home_conference": team_conf if not is_away else None,  # We know our team's conf
            "away_conference": team_conf if is_away else None,
            "home_ap_rank": None,  # Will need to fill from rankings table
            "away_ap_rank": None,
            "home_score": home_score,
            "away_score": away_score,
            "same_conference": False,  # Will compute later
            "ranked_vs_unranked": False,  # Will compute later
            "source": "cbbpy_schedule",
        }

    except Exception as e:
        return None


def scrape_season_fast(season: int) -> pd.DataFrame:
    """Scrape all major conference games for a season using team schedules."""
    if cbb is None:
        raise ImportError("CBBpy required for scraping")

    print(f"\nScraping season {season-1}-{str(season)[2:]}...")

    all_games = {}  # Use dict to deduplicate by game_id

    for conf in CONFERENCES:
        conf_name = CONF_NAMES.get(conf, conf)
        print(f"  {conf_name}...", end=" ", flush=True)

        teams = get_conference_teams(conf, season)
        if not teams:
            print("no teams found")
            continue

        conf_games = 0
        for team in teams:
            games = scrape_team_schedule(team, season, conf_name)
            for g in games:
                if g['game_id'] not in all_games:
                    all_games[g['game_id']] = g
                    conf_games += 1
            time.sleep(0.2)  # Brief pause between teams

        print(f"{len(teams)} teams, {conf_games} new games")
        time.sleep(0.5)

    # Convert to DataFrame
    df = pd.DataFrame(list(all_games.values()))

    if not df.empty:
        # Try to determine same-conference games
        # A game is same-conference if both teams are in the same conference
        # We only know the conference of teams we scraped
        # For now, mark as same_conference if both teams' conferences match
        df['same_conference'] = df.apply(
            lambda r: r['home_conference'] == r['away_conference']
                      and r['home_conference'] is not None,
            axis=1
        )

    print(f"Season {season}: {len(df)} total games")
    return df


def save_games_to_db(df: pd.DataFrame):
    """Save games DataFrame to SQLite database."""
    if df.empty:
        print("No games to save")
        return

    conn = get_connection()

    df = df.copy()
    df["same_conference"] = df["same_conference"].astype(int)
    df["ranked_vs_unranked"] = df["ranked_vs_unranked"].astype(int)

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


def scrape_multiple_seasons(start_year: int, end_year: int):
    """Scrape multiple seasons."""
    init_database()

    all_games = []

    for season in range(start_year, end_year + 1):
        try:
            df = scrape_season_fast(season)

            if not df.empty:
                all_games.append(df)
                save_games_to_csv(df, f"games_{season}.csv")
                save_games_to_db(df)

            print(f"Completed season {season}\n")
            time.sleep(2)

        except Exception as e:
            print(f"Failed to scrape season {season}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if all_games:
        combined = pd.concat(all_games, ignore_index=True)
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

    if 'date' in df.columns and not df['date'].isna().all():
        print(f"Date range: {df['date'].min()} to {df['date'].max()}")

    print(f"\nSame-conference games: {df['same_conference'].sum()}")

    print(f"\nGames per conference:")
    conf_counts = df[df['home_conference'].notna()]['home_conference'].value_counts()
    for conf, count in conf_counts.items():
        print(f"  {conf}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Fast NCAA basketball game scraper")
    parser.add_argument(
        "--years", type=str, help="Year range (e.g., 2020-2024)", default="2020-2024"
    )
    parser.add_argument("--year", type=int, help="Single year to scrape")
    parser.add_argument("--validate", action="store_true", help="Validate existing data")

    args = parser.parse_args()

    if args.validate:
        data_path = Path(__file__).parent.parent / "data" / "raw"
        csv_files = list(data_path.glob("games_*.csv"))
        if csv_files:
            df = pd.concat([pd.read_csv(f) for f in csv_files])
            validate_data(df)
        else:
            print("No data files found.")
        return

    if args.year:
        df = scrape_season_fast(args.year)
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

"""
Database schema for Conference Contrarian.

SQLite database with three main tables:
- games: All NCAA basketball games with rankings and betting data
- ap_rankings: Weekly AP Poll snapshots
- predictions: Model predictions and results tracking
"""

import sqlite3
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "data" / "contrarian.db"


def get_connection():
    """Get database connection with row factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    """Initialize database with all tables."""
    conn = get_connection()
    cursor = conn.cursor()

    # Games table - core data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id TEXT PRIMARY KEY,
            date DATE NOT NULL,
            season INTEGER NOT NULL,

            -- Teams
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_conference TEXT,
            away_conference TEXT,

            -- Rankings at time of game (NULL = unranked)
            home_ap_rank INTEGER,
            away_ap_rank INTEGER,

            -- Final scores
            home_score INTEGER,
            away_score INTEGER,

            -- Betting lines
            spread REAL,              -- Positive = home is underdog
            over_under REAL,
            closing_spread REAL,      -- Closing line if different

            -- Results
            spread_result TEXT,       -- 'home_cover', 'away_cover', 'push'
            ou_result TEXT,           -- 'over', 'under', 'push'

            -- Derived flags
            same_conference BOOLEAN DEFAULT 0,
            ranked_vs_unranked BOOLEAN DEFAULT 0,

            -- Metadata
            venue TEXT,               -- 'home', 'away', 'neutral'
            source TEXT,              -- 'cbbpy', 'sportsref', etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # AP Rankings table - weekly snapshots
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ap_rankings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            poll_date DATE NOT NULL,

            team TEXT NOT NULL,
            rank INTEGER NOT NULL,
            first_place_votes INTEGER,
            total_points INTEGER,
            previous_rank INTEGER,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(season, week, team)
        )
    """)

    # Predictions table - model output tracking
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT REFERENCES games(game_id),
            prediction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Model info
            model_version TEXT NOT NULL,
            model_type TEXT,          -- 'logistic', 'xgboost', etc.

            -- Prediction output
            predicted_cover_prob REAL,    -- P(underdog covers)
            confidence_tier TEXT,         -- 'high', 'medium', 'low'

            -- Bet recommendation
            recommended_bet TEXT,         -- 'underdog', 'favorite', 'pass'
            edge_pct REAL,               -- Expected edge over market
            kelly_fraction REAL,         -- Recommended bet size (0-1)

            -- Actual result (filled after game)
            actual_result TEXT,          -- 'win', 'loss', 'push'
            profit_loss REAL,

            -- Features used (JSON for debugging)
            features_json TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Indices for common queries
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_date ON games(date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_season ON games(season)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_conference ON games(same_conference)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_games_ranked ON games(ranked_vs_unranked)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_rankings_season_week ON ap_rankings(season, week)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_predictions_game ON predictions(game_id)")

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")


def drop_all_tables():
    """Drop all tables (use with caution)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS predictions")
    cursor.execute("DROP TABLE IF EXISTS ap_rankings")
    cursor.execute("DROP TABLE IF EXISTS games")
    conn.commit()
    conn.close()
    print("All tables dropped")


if __name__ == "__main__":
    init_database()

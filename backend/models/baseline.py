"""
Baseline Model for Conference Contrarian

Simple logistic regression to predict P(underdog covers).
Only build/use if edge validates in validate_edge.py.

Features:
- favorite_rank: AP ranking of favorite (lower = better)
- rank_tier: Categorical (1-5, 6-15, 16-25)
- is_home: 1 if underdog is home team, 0 otherwise
- season_progress: 0-1 (early vs late season)

Usage:
    python baseline.py --train
    python baseline.py --predict
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.metrics import classification_report, roc_auc_score
import joblib

sys.path.insert(0, str(Path(__file__).parent.parent))

from data_collection.schema import get_connection
from analysis.validate_edge import filter_target_games, identify_underdog


MODEL_PATH = Path(__file__).parent / "baseline_model.pkl"
MODEL_VERSION = "v1.0.0"


def prepare_features(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Engineer features for each game.

    Returns (X, y) where:
    - X: Feature DataFrame
    - y: Binary target (1 = underdog cover/win, 0 = loss)
    """
    features = []
    targets = []

    for _, row in df.iterrows():
        underdog_info = identify_underdog(row)
        if not underdog_info:
            continue

        # Features
        favorite_rank = underdog_info["favorite_rank"]
        is_home = 1 if underdog_info["underdog"] == "home" else 0

        # Season progress (assuming Nov 1 start, Apr 15 end)
        try:
            game_date = pd.to_datetime(row["date"])
            season_start = datetime(game_date.year if game_date.month >= 11 else game_date.year - 1, 11, 1)
            days_into_season = (game_date - season_start).days
            season_progress = min(1.0, max(0.0, days_into_season / 165))
        except:
            season_progress = 0.5

        # Rank tier (categorical encoded)
        if favorite_rank <= 5:
            rank_tier = 1  # Top 5
        elif favorite_rank <= 15:
            rank_tier = 2  # 6-15
        else:
            rank_tier = 3  # 16-25

        features.append({
            "favorite_rank": favorite_rank,
            "rank_tier": rank_tier,
            "is_home": is_home,
            "season_progress": season_progress,
            "rank_inverse": 26 - favorite_rank,  # Higher = better opponent
        })

        # Target: did underdog win/cover?
        actual_margin = underdog_info["underdog_score"] - underdog_info["favorite_score"]
        targets.append(1 if actual_margin > 0 else 0)

    X = pd.DataFrame(features)
    y = pd.Series(targets)

    return X, y


def train_model(df: pd.DataFrame) -> LogisticRegression:
    """
    Train logistic regression with time-series cross-validation.
    """
    X, y = prepare_features(df)

    if len(X) < 100:
        print("WARNING: Small sample size, results may be unreliable")

    print(f"Training on {len(X)} samples")
    print(f"Class distribution: {y.mean():.2%} wins")

    # Time-series split (respects temporal ordering)
    tscv = TimeSeriesSplit(n_splits=5)

    model = LogisticRegression(
        random_state=42,
        max_iter=1000,
        class_weight="balanced",  # Handle class imbalance
    )

    # Cross-validation
    scores = cross_val_score(model, X, y, cv=tscv, scoring="accuracy")
    auc_scores = cross_val_score(model, X, y, cv=tscv, scoring="roc_auc")

    print(f"\nCross-validation results (5-fold time series):")
    print(f"  Accuracy: {scores.mean():.3f} (+/- {scores.std():.3f})")
    print(f"  AUC-ROC:  {auc_scores.mean():.3f} (+/- {auc_scores.std():.3f})")

    # Train on full dataset
    model.fit(X, y)

    # Feature importance
    print(f"\nFeature coefficients:")
    for name, coef in zip(X.columns, model.coef_[0]):
        print(f"  {name}: {coef:.4f}")

    return model


def save_model(model: LogisticRegression):
    """Save trained model to disk."""
    joblib.dump({
        "model": model,
        "version": MODEL_VERSION,
        "trained_at": datetime.now().isoformat(),
    }, MODEL_PATH)
    print(f"\nModel saved to {MODEL_PATH}")


def load_model() -> LogisticRegression:
    """Load trained model from disk."""
    data = joblib.load(MODEL_PATH)
    print(f"Loaded model version {data['version']} (trained {data['trained_at']})")
    return data["model"]


def backtest_roi(df: pd.DataFrame, model: LogisticRegression, threshold: float = 0.55):
    """
    Backtest ROI if we only bet on high-confidence predictions.

    Args:
        df: Games DataFrame
        model: Trained model
        threshold: Minimum probability to place bet (default 55%)
    """
    X, y = prepare_features(df)
    probs = model.predict_proba(X)[:, 1]  # P(underdog wins)

    # Filter to high-confidence predictions
    high_conf_mask = probs >= threshold
    bets_placed = high_conf_mask.sum()

    if bets_placed == 0:
        print(f"No bets at {threshold:.0%} threshold")
        return

    bets_won = y[high_conf_mask].sum()

    # Assume -110 odds (risk $110 to win $100)
    profit_if_win = 100
    loss_if_lose = 110

    total_profit = bets_won * profit_if_win - (bets_placed - bets_won) * loss_if_lose
    total_wagered = bets_placed * loss_if_lose
    roi = total_profit / total_wagered

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS (threshold: {threshold:.0%})")
    print(f"{'='*60}")
    print(f"Bets placed: {bets_placed}")
    print(f"Bets won: {bets_won} ({bets_won/bets_placed:.1%})")
    print(f"Total wagered: ${total_wagered:,.0f}")
    print(f"Net profit: ${total_profit:,.0f}")
    print(f"ROI: {roi:.2%}")

    # Kelly Criterion suggested bet size
    win_rate = bets_won / bets_placed
    b = profit_if_win / loss_if_lose  # Decimal odds - 1
    q = 1 - win_rate
    kelly = (win_rate * b - q) / b if b > 0 else 0
    print(f"\nKelly Criterion: {max(0, kelly):.2%} of bankroll per bet")

    return {"roi": roi, "bets": bets_placed, "wins": bets_won, "win_rate": bets_won/bets_placed}


def predict_game(model: LogisticRegression, game: dict) -> dict:
    """
    Predict outcome for a single game.

    Args:
        model: Trained model
        game: Dict with favorite_rank, is_home, season_progress

    Returns:
        Dict with prediction and confidence
    """
    X = pd.DataFrame([{
        "favorite_rank": game["favorite_rank"],
        "rank_tier": 1 if game["favorite_rank"] <= 5 else (2 if game["favorite_rank"] <= 15 else 3),
        "is_home": game.get("is_home", 0),
        "season_progress": game.get("season_progress", 0.5),
        "rank_inverse": 26 - game["favorite_rank"],
    }])

    prob = model.predict_proba(X)[0, 1]

    # Determine recommendation
    if prob >= 0.60:
        recommendation = "BET_UNDERDOG"
        confidence = "HIGH"
    elif prob >= 0.55:
        recommendation = "LEAN_UNDERDOG"
        confidence = "MEDIUM"
    else:
        recommendation = "PASS"
        confidence = "LOW"

    return {
        "cover_probability": prob,
        "recommendation": recommendation,
        "confidence": confidence,
        "edge_vs_breakeven": prob - 0.524,
    }


def main():
    parser = argparse.ArgumentParser(description="Train/use baseline model")
    parser.add_argument("--train", action="store_true", help="Train new model")
    parser.add_argument("--backtest", action="store_true", help="Run backtest")
    parser.add_argument("--threshold", type=float, default=0.55, help="Bet threshold")

    args = parser.parse_args()

    # Load data
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT * FROM games WHERE home_score IS NOT NULL",
        conn
    )
    conn.close()

    target_df = filter_target_games(df)
    print(f"Target games: {len(target_df)}")

    if args.train:
        model = train_model(target_df)
        save_model(model)

        # Run backtest automatically after training
        print("\nRunning backtest...")
        for threshold in [0.50, 0.55, 0.60]:
            backtest_roi(target_df, model, threshold)

    elif args.backtest:
        model = load_model()
        backtest_roi(target_df, model, args.threshold)

    else:
        # Demo prediction
        if MODEL_PATH.exists():
            model = load_model()
            demo = predict_game(model, {"favorite_rank": 10, "is_home": 1})
            print(f"\nDemo prediction (rank 10 favorite vs home underdog):")
            print(f"  Cover probability: {demo['cover_probability']:.2%}")
            print(f"  Recommendation: {demo['recommendation']}")
            print(f"  Edge: {demo['edge_vs_breakeven']:.2%}")
        else:
            print("No trained model found. Run with --train first.")


if __name__ == "__main__":
    main()

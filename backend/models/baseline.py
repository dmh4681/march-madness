"""
Baseline Model for Conference Contrarian
=========================================

This module implements the core machine learning prediction model used to estimate
the probability that an underdog will cover the spread in NCAA basketball games.

Mathematical Foundation
=======================

The model uses logistic regression, which estimates the probability of a binary
outcome (underdog covers vs doesn't cover) using the logistic function:

    P(cover) = 1 / (1 + e^(-z))

where z = β₀ + β₁·x₁ + β₂·x₂ + ... + βₙ·xₙ

The model learns the coefficients (β values) from historical data to maximize
the likelihood of observed outcomes.

Why Logistic Regression?
========================

1. **Interpretability**: Coefficients have meaningful interpretations
   - Positive coefficient = feature increases cover probability
   - Magnitude indicates strength of relationship

2. **Probabilistic Output**: Directly outputs probabilities (0-1)
   - Essential for betting: need P(cover) to determine edge
   - Compare to implied probability from betting line

3. **Works with Small Data**: Effective with hundreds of samples
   - NCAA basketball has limited high-stakes games per season
   - More complex models would overfit

4. **Class Imbalance Handling**: Built-in class_weight parameter
   - Underdogs don't cover exactly 50% of the time
   - Balancing prevents bias toward majority class

Feature Engineering
===================

The model uses carefully selected features based on betting theory:

1. **favorite_rank** (continuous, 1-25)
   - AP ranking of the favorite team
   - Lower rank = better team
   - Hypothesis: Higher-ranked favorites get more public attention,
     potentially inflating their lines

2. **rank_tier** (categorical, 1-3)
   - 1 = Top 5 teams (blue bloods, heavy favorites)
   - 2 = Ranked 6-15 (solid but not elite)
   - 3 = Ranked 16-25 (bubble teams)
   - Different tiers have different public betting patterns

3. **is_home** (binary, 0-1)
   - 1 if underdog is home team, 0 if away
   - Home underdogs historically perform better
   - Home court advantage in college: ~3-4 points

4. **season_progress** (continuous, 0-1)
   - 0 = early season (November)
   - 1 = late season (March)
   - Teams improve/regress as season progresses
   - Late-season games have more meaningful data

5. **rank_inverse** (derived, 1-25)
   - 26 - favorite_rank
   - Higher values = better opponent
   - Provides linear relationship for model

Betting Theory Background
=========================

The "Conference Contrarian" strategy is based on market inefficiency theory:

**Public Betting Bias:**
When a ranked team faces an unranked conference opponent:
- Public money flows heavily toward the ranked team
- Sportsbooks adjust lines to balance action
- This can create value on the underdog

**The 52.4% Threshold:**
At standard -110 odds (risk $110 to win $100):
- Breakeven win rate = 110 / (110 + 100) = 52.38%
- Any strategy with win rate > 52.4% is profitable long-term

**Conference Game Dynamics:**
In conference play, familiarity reduces variance:
- Teams have played each other before
- Coaches know opponents' tendencies
- Recruiting pipelines create competitive balance

Confidence Tiers and Edge Calculation
=====================================

The model's output probability is converted to betting recommendations:

**Edge Calculation:**
    edge = |P(cover) - 0.5| × 100

This represents the percentage advantage over a coin flip.

**Confidence Tier Assignment:**
- **HIGH** (P >= 0.60): Strong conviction, edge > 10%
  - Clear statistical advantage
  - Recommended for larger unit bets

- **MEDIUM** (0.55 <= P < 0.60): Moderate conviction, edge 5-10%
  - Good value exists
  - Standard 1-unit bet recommended

- **LOW/PASS** (P < 0.55): Weak or no edge
  - Near breakeven or worse
  - No bet recommended

Kelly Criterion for Bet Sizing
==============================

The model includes Kelly Criterion calculation for optimal bet sizing:

    f* = (bp - q) / b

where:
- f* = fraction of bankroll to wager
- b = decimal odds received (at -110: b = 100/110 ≈ 0.91)
- p = probability of winning
- q = probability of losing (1 - p)

Example at 55% win rate:
    f* = (0.91 × 0.55 - 0.45) / 0.91
    f* = (0.50 - 0.45) / 0.91
    f* = 0.055 (5.5% of bankroll)

Note: Full Kelly is aggressive; many bettors use "half Kelly" or "quarter Kelly".

Model Training
==============

Training uses time-series cross-validation to respect temporal ordering:
- Can't use future games to predict past games
- 5-fold split maintains chronological order
- Prevents lookahead bias

Evaluation Metrics:
- **Accuracy**: Percentage of correct predictions
- **AUC-ROC**: Area under ROC curve (0.5 = random, 1.0 = perfect)
- **Profit/ROI**: Actual betting performance in backtest

Model Persistence
=================

Trained models are serialized using joblib and stored with metadata:
- Model version for tracking
- Training timestamp
- Can be loaded for inference without retraining

Usage Examples
==============

```python
# Train a new model
python baseline.py --train

# Run backtest with custom threshold
python baseline.py --backtest --threshold 0.58

# Make a prediction (requires trained model)
from baseline import load_model, predict_game
model = load_model()
result = predict_game(model, {
    "favorite_rank": 10,
    "is_home": 1,  # underdog is home
    "season_progress": 0.6
})
print(f"Cover probability: {result['cover_probability']:.2%}")
print(f"Recommendation: {result['recommendation']}")
```

Dependencies
============

- scikit-learn: Model implementation and cross-validation
- pandas: Data manipulation
- numpy: Numerical operations
- joblib: Model serialization

See Also
========

- validate_edge.py: Statistical validation of betting edge
- daily_refresh.py: Integration with prediction pipeline
- api/main.py: API endpoints serving predictions
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

    Feature Engineering Process:
    ===========================
    This function transforms raw game data into model-ready features.
    Each feature is designed to capture a specific betting signal.

    Feature Scaling Notes:
    - favorite_rank: Natural scale (1-25), no scaling needed
    - rank_tier: Ordinal encoding (1, 2, 3) - treated as continuous
    - is_home: Binary (0, 1) - no scaling needed
    - season_progress: Already scaled to [0, 1]
    - rank_inverse: Linear transformation of favorite_rank

    Logistic regression is relatively robust to scale differences,
    but standardization could be added if using regularization.

    Args:
        df: DataFrame containing game data with columns:
            - date: Game date
            - home_ap_rank / away_ap_rank: AP rankings
            - home_score / away_score: Final scores
            - same_conference / ranked_vs_unranked: Filter flags

    Returns:
        Tuple of (X, y) where:
        - X: Feature matrix (n_samples, n_features)
        - y: Binary target vector (1 = underdog covered, 0 = didn't cover)
    """
    features = []
    targets = []

    for _, row in df.iterrows():
        underdog_info = identify_underdog(row)
        if not underdog_info:
            continue

        # =================================================================
        # FEATURE 1: Favorite Rank (continuous, 1-25)
        # =================================================================
        # The AP ranking of the favorite team
        # Lower values = better teams (rank 1 is best)
        # Hypothesis: Top-ranked favorites may be overvalued by public
        favorite_rank = underdog_info["favorite_rank"]

        # =================================================================
        # FEATURE 2: Is Home (binary, 0 or 1)
        # =================================================================
        # Whether the underdog is the home team
        # Home court advantage in college basketball: ~3-4 points
        # Home underdogs may be systematically undervalued
        is_home = 1 if underdog_info["underdog"] == "home" else 0

        # =================================================================
        # FEATURE 3: Season Progress (continuous, 0-1)
        # =================================================================
        # How far into the season the game occurs
        # Early season (Nov): Less reliable team data, more variance
        # Late season (Mar): Teams are well-known, less market inefficiency
        #
        # NCAA season: ~November 1 to ~April 15 (165 days)
        try:
            game_date = pd.to_datetime(row["date"])
            # Determine season start (November of current or previous year)
            season_start = datetime(game_date.year if game_date.month >= 11 else game_date.year - 1, 11, 1)
            days_into_season = (game_date - season_start).days
            # Clamp to [0, 1] range
            season_progress = min(1.0, max(0.0, days_into_season / 165))
        except:
            # Default to mid-season if date parsing fails
            season_progress = 0.5

        # =================================================================
        # FEATURE 4: Rank Tier (ordinal, 1-3)
        # =================================================================
        # Categorical grouping of favorite's ranking
        # Different tiers have different public betting patterns:
        # - Tier 1 (Top 5): "Blue bloods" - heavy public favorites
        # - Tier 2 (6-15): Solid teams, moderate attention
        # - Tier 3 (16-25): Bubble teams, less public interest
        if favorite_rank <= 5:
            rank_tier = 1  # Top 5 - highest public attention
        elif favorite_rank <= 15:
            rank_tier = 2  # 6-15 - moderate attention
        else:
            rank_tier = 3  # 16-25 - lower attention

        # =================================================================
        # FEATURE 5: Rank Inverse (derived, 1-25)
        # =================================================================
        # Linear transformation: 26 - favorite_rank
        # Higher values = better opponent (rank 1 -> 25, rank 25 -> 1)
        # Provides alternative parameterization for model to learn from

        features.append({
            "favorite_rank": favorite_rank,
            "rank_tier": rank_tier,
            "is_home": is_home,
            "season_progress": season_progress,
            "rank_inverse": 26 - favorite_rank,
        })

        # =================================================================
        # TARGET: Did Underdog Win/Cover?
        # =================================================================
        # Binary classification target:
        # - 1: Underdog won outright (or covered spread if spread data available)
        # - 0: Underdog lost
        #
        # Margin = underdog_score - favorite_score
        # Positive margin = underdog won
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

    Backtesting Methodology
    =======================
    This function simulates betting performance using historical data.
    It answers: "If we had bet on games where P(cover) >= threshold,
    what would our return have been?"

    Important Caveats:
    - Uses straight-up wins as proxy for ATS covers (slight underestimate)
    - Assumes -110 odds on all bets (standard, but may vary)
    - Does not account for line movement or timing
    - Past performance does not guarantee future results

    ROI Calculation
    ===============
    ROI (Return on Investment) measures profitability:

        ROI = (Total Profit) / (Total Wagered) × 100%

    At -110 odds:
    - Risk $110 to win $100
    - Breakeven requires 52.4% win rate
    - 55% win rate → ~4.5% ROI
    - 60% win rate → ~13.6% ROI

    Kelly Criterion
    ===============
    The Kelly formula calculates optimal bet sizing to maximize
    long-term bankroll growth while avoiding ruin:

        f* = (bp - q) / b

    where:
    - f* = optimal fraction of bankroll to bet
    - b = net odds received (profit/risk ratio)
    - p = probability of winning
    - q = probability of losing (1 - p)

    Example:
    - Win rate: 55% (p = 0.55, q = 0.45)
    - Odds: -110 (b = 100/110 ≈ 0.909)
    - Kelly: (0.909 × 0.55 - 0.45) / 0.909 ≈ 5.5%

    Practical Adjustments:
    - Full Kelly is aggressive and assumes perfect probability estimates
    - "Half Kelly" (f*/2) is more conservative
    - "Quarter Kelly" (f*/4) for additional safety margin

    Args:
        df: Games DataFrame with historical results
        model: Trained LogisticRegression model
        threshold: Minimum P(cover) to place bet (default 55%)
                   Higher threshold = fewer bets, higher win rate
                   Lower threshold = more bets, lower win rate

    Returns:
        Dict with backtest metrics or None if no bets placed
    """
    X, y = prepare_features(df)
    probs = model.predict_proba(X)[:, 1]  # P(underdog wins)

    # =================================================================
    # STEP 1: Filter to High-Confidence Predictions
    # =================================================================
    # Only bet when model probability exceeds threshold
    # This is the core of selective betting - quality over quantity
    high_conf_mask = probs >= threshold
    bets_placed = high_conf_mask.sum()

    if bets_placed == 0:
        print(f"No bets at {threshold:.0%} threshold")
        return

    bets_won = y[high_conf_mask].sum()

    # =================================================================
    # STEP 2: Calculate Profit/Loss at Standard Odds
    # =================================================================
    # Standard sportsbook odds: -110 (risk $110 to win $100)
    # This is the industry standard and accounts for the "vig" or "juice"
    profit_if_win = 100   # Win $100 on a winning bet
    loss_if_lose = 110    # Lose $110 on a losing bet

    # Total profit = wins × profit_per_win - losses × loss_per_loss
    total_profit = bets_won * profit_if_win - (bets_placed - bets_won) * loss_if_lose

    # Total wagered = number of bets × amount risked per bet
    total_wagered = bets_placed * loss_if_lose

    # ROI = profit / wagered (can be negative)
    roi = total_profit / total_wagered

    print(f"\n{'='*60}")
    print(f"BACKTEST RESULTS (threshold: {threshold:.0%})")
    print(f"{'='*60}")
    print(f"Bets placed: {bets_placed}")
    print(f"Bets won: {bets_won} ({bets_won/bets_placed:.1%})")
    print(f"Total wagered: ${total_wagered:,.0f}")
    print(f"Net profit: ${total_profit:,.0f}")
    print(f"ROI: {roi:.2%}")

    # =================================================================
    # STEP 3: Kelly Criterion Calculation
    # =================================================================
    # Optimal bet sizing based on observed win rate
    win_rate = bets_won / bets_placed
    b = profit_if_win / loss_if_lose  # Net odds ratio (~0.909 at -110)
    q = 1 - win_rate                   # Probability of losing

    # Kelly formula: f* = (bp - q) / b
    # - If positive: bet this fraction of bankroll
    # - If negative: no edge exists, don't bet
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

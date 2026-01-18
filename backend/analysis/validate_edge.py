"""
Edge Validation Script

Tests the core hypothesis:
Do unranked conference underdogs cover at >52.4%?

This is the most important script in the project.
If edge doesn't validate, don't build anything else.

Usage:
    python validate_edge.py
    python validate_edge.py --csv path/to/games.csv
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_collection.schema import get_connection


# Breakeven threshold at -110 odds
BREAKEVEN_PCT = 0.524


def load_games_from_db() -> pd.DataFrame:
    """Load games data from SQLite database."""
    conn = get_connection()
    query = """
        SELECT *
        FROM games
        WHERE home_score IS NOT NULL
        AND away_score IS NOT NULL
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def load_games_from_csv(filepath: str) -> pd.DataFrame:
    """Load games data from CSV file."""
    return pd.read_csv(filepath)


def filter_target_games(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filter to our target dataset:
    - Same conference matchups
    - One team ranked, one team unranked
    """
    # Ensure boolean columns
    if df["same_conference"].dtype != bool:
        df["same_conference"] = df["same_conference"].astype(bool)
    if df["ranked_vs_unranked"].dtype != bool:
        df["ranked_vs_unranked"] = df["ranked_vs_unranked"].astype(bool)

    target = df[(df["same_conference"] == True) & (df["ranked_vs_unranked"] == True)]

    return target.copy()


def identify_underdog(row: pd.Series) -> dict:
    """
    Identify which team is the underdog and if they're unranked.

    Without spread data, we use rankings:
    - Ranked team is assumed to be favorite
    - Unranked team is assumed to be underdog

    Returns dict with underdog info.
    """
    home_ranked = pd.notna(row["home_ap_rank"])
    away_ranked = pd.notna(row["away_ap_rank"])

    # In ranked vs unranked, the unranked team is the underdog
    if home_ranked and not away_ranked:
        # Home is ranked (favorite), away is unranked (underdog)
        return {
            "underdog": "away",
            "underdog_team": row["away_team"],
            "favorite_team": row["home_team"],
            "favorite_rank": row["home_ap_rank"],
            "underdog_score": row["away_score"],
            "favorite_score": row["home_score"],
        }
    elif away_ranked and not home_ranked:
        # Away is ranked (favorite), home is unranked (underdog)
        return {
            "underdog": "home",
            "underdog_team": row["home_team"],
            "favorite_team": row["away_team"],
            "favorite_rank": row["away_ap_rank"],
            "underdog_score": row["home_score"],
            "favorite_score": row["away_score"],
        }
    else:
        return None


def calculate_ats_result(row: pd.Series, spread: float = None) -> str:
    """
    Calculate ATS result for underdog.

    If no spread available, use a proxy spread based on ranking.
    Common proxy: ranked team favored by ~5-10 points in conference games.

    Returns: 'cover', 'loss', or 'push'
    """
    underdog_info = identify_underdog(row)
    if not underdog_info:
        return None

    # Calculate actual margin (from underdog perspective)
    actual_margin = underdog_info["underdog_score"] - underdog_info["favorite_score"]

    # If we have spread data, use it
    if spread is not None:
        # Spread is typically expressed as "favorite -X"
        # So underdog covers if they lose by less than X or win
        if actual_margin > -spread:
            return "cover"
        elif actual_margin < -spread:
            return "loss"
        else:
            return "push"

    # Without spread, calculate straight-up win/loss
    # This is a proxy - ideally we'd have real spread data
    if actual_margin > 0:
        return "win"  # Underdog won outright
    elif actual_margin < 0:
        return "loss"  # Underdog lost
    else:
        return "push"


def validate_edge(df: pd.DataFrame, use_spread: bool = False) -> dict:
    """
    Core edge validation function.

    Tests if unranked conference underdogs perform better than expected.

    Args:
        df: Games DataFrame (already filtered to target games)
        use_spread: Whether to use spread data (if available)

    Returns:
        Dict with validation results
    """
    results = []

    for _, row in df.iterrows():
        underdog_info = identify_underdog(row)
        if not underdog_info:
            continue

        # Get spread if available and requested
        spread = None
        if use_spread and "spread" in df.columns:
            spread = row.get("spread")
            if pd.isna(spread):
                spread = None

        # Calculate result
        result = calculate_ats_result(row, spread)
        if result is None:
            continue

        results.append(
            {
                "game_id": row.get("game_id"),
                "date": row.get("date"),
                "underdog_team": underdog_info["underdog_team"],
                "favorite_team": underdog_info["favorite_team"],
                "favorite_rank": underdog_info["favorite_rank"],
                "underdog_score": underdog_info["underdog_score"],
                "favorite_score": underdog_info["favorite_score"],
                "result": result,
                "spread": spread,
            }
        )

    if not results:
        return {"error": "No valid games found"}

    results_df = pd.DataFrame(results)

    # Calculate statistics
    if use_spread:
        # ATS analysis
        covers = (results_df["result"] == "cover").sum()
        losses = (results_df["result"] == "loss").sum()
        pushes = (results_df["result"] == "push").sum()
        total = covers + losses  # Exclude pushes from percentage
    else:
        # Straight-up analysis (proxy for ATS)
        covers = (results_df["result"] == "win").sum()
        losses = (results_df["result"] == "loss").sum()
        pushes = (results_df["result"] == "push").sum()
        total = covers + losses

    if total == 0:
        return {"error": "No games with results"}

    win_pct = covers / total

    # Statistical tests
    # Binomial test: H0 = 50%, H1 > 50%
    binom_result = stats.binomtest(covers, total, p=0.5, alternative="greater")
    p_value = binom_result.pvalue

    # Wilson confidence interval (better for proportions)
    ci_low, ci_high = wilson_confidence_interval(covers, total, confidence=0.95)

    # Is edge significant?
    edge_exists = win_pct > BREAKEVEN_PCT and p_value < 0.05

    return {
        "sample_size": total,
        "pushes": pushes,
        "wins": covers,
        "losses": losses,
        "win_percentage": win_pct,
        "p_value": p_value,
        "ci_95_low": ci_low,
        "ci_95_high": ci_high,
        "breakeven_threshold": BREAKEVEN_PCT,
        "edge_exists": edge_exists,
        "results_df": results_df,
        "analysis_type": "ATS" if use_spread else "Straight-Up (proxy)",
    }


def wilson_confidence_interval(successes: int, trials: int, confidence: float = 0.95):
    """
    Calculate Wilson score confidence interval for a proportion.
    More accurate than normal approximation for small samples.
    """
    if trials == 0:
        return (0, 0)

    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / trials

    denominator = 1 + z**2 / trials
    center = (p_hat + z**2 / (2 * trials)) / denominator
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * trials)) / trials) / denominator

    return (center - margin, center + margin)


def analyze_by_spread_size(results_df: pd.DataFrame) -> dict:
    """
    Break down results by spread/ranking tiers.

    Without spread data, use ranking as proxy.
    """
    breakdowns = {}

    # By favorite ranking tier
    for min_rank, max_rank, label in [(1, 5, "Top 5"), (6, 15, "6-15"), (16, 25, "16-25")]:
        tier_games = results_df[
            (results_df["favorite_rank"] >= min_rank)
            & (results_df["favorite_rank"] <= max_rank)
        ]

        if len(tier_games) == 0:
            continue

        wins = (tier_games["result"].isin(["cover", "win"])).sum()
        total = len(tier_games[~tier_games["result"].isin(["push"])])

        if total > 0:
            breakdowns[label] = {
                "wins": wins,
                "total": total,
                "win_pct": wins / total,
            }

    return breakdowns


def print_results(results: dict):
    """Pretty print validation results."""
    print("\n" + "=" * 70)
    print("EDGE VALIDATION RESULTS")
    print("=" * 70)

    if "error" in results:
        print(f"\nError: {results['error']}")
        return

    print(f"\nAnalysis Type: {results['analysis_type']}")
    print(f"\nSample Size: {results['sample_size']} games")
    print(f"Wins: {results['wins']}")
    print(f"Losses: {results['losses']}")
    print(f"Pushes: {results['pushes']}")

    print(f"\nWin Percentage: {results['win_percentage']:.2%}")
    print(f"Breakeven Threshold: {results['breakeven_threshold']:.2%}")
    print(f"P-Value: {results['p_value']:.4f}")
    print(f"95% Confidence Interval: {results['ci_95_low']:.2%} - {results['ci_95_high']:.2%}")

    print("\n" + "-" * 70)
    if results["edge_exists"]:
        print("RESULT: EDGE EXISTS")
        print(f"  Win rate ({results['win_percentage']:.2%}) > Breakeven ({BREAKEVEN_PCT:.2%})")
        print(f"  P-value ({results['p_value']:.4f}) < 0.05")
        print("\n  PROCEED TO PHASE 2: MODEL DEVELOPMENT")
    else:
        print("RESULT: EDGE NOT VALIDATED")

        if results["win_percentage"] <= BREAKEVEN_PCT:
            print(f"  Win rate ({results['win_percentage']:.2%}) <= Breakeven ({BREAKEVEN_PCT:.2%})")
        if results["p_value"] >= 0.05:
            print(f"  P-value ({results['p_value']:.4f}) >= 0.05 (not significant)")

        print("\n  RECOMMENDATION: Explore alternative hypotheses")
    print("-" * 70)

    # Breakdown by tier
    if "results_df" in results:
        print("\nBREAKDOWN BY FAVORITE RANKING:")
        breakdowns = analyze_by_spread_size(results["results_df"])
        for tier, data in breakdowns.items():
            print(f"  {tier}: {data['win_pct']:.2%} ({data['wins']}/{data['total']})")


def main():
    parser = argparse.ArgumentParser(description="Validate betting edge hypothesis")
    parser.add_argument("--csv", type=str, help="Path to games CSV file")
    parser.add_argument(
        "--use-spread", action="store_true", help="Use spread data if available"
    )

    args = parser.parse_args()

    # Load data
    if args.csv:
        print(f"Loading data from {args.csv}...")
        df = load_games_from_csv(args.csv)
    else:
        print("Loading data from database...")
        df = load_games_from_db()

    print(f"Total games loaded: {len(df)}")

    # Filter to target games
    target_df = filter_target_games(df)
    print(f"Target games (same conf, ranked vs unranked): {len(target_df)}")

    if len(target_df) < 50:
        print("\nWARNING: Sample size too small for reliable analysis")
        print("Need at least 500 games for statistical significance")

    # Run validation
    results = validate_edge(target_df, use_spread=args.use_spread)

    # Print results
    print_results(results)

    # Save results to file
    if "results_df" in results:
        output_path = Path(__file__).parent.parent / "data" / "processed" / "validation_results.csv"
        results["results_df"].to_csv(output_path, index=False)
        print(f"\nDetailed results saved to {output_path}")


if __name__ == "__main__":
    main()

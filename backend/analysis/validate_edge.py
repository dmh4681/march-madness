"""
Edge Validation Script

Tests the core betting hypothesis that powers Conference Contrarian:
Do unranked conference underdogs cover at >52.4%?

Background: The Conference Contrarian Strategy
=============================================
The strategy is based on the observation that when a ranked team plays
an unranked team from the same conference:
1. The betting public overvalues the ranked team's status
2. Conference familiarity reduces the talent gap
3. Unranked teams at home are especially undervalued
4. This creates a systematic edge on the underdog

The 52.4% Threshold
==================
At standard -110 odds (risk $110 to win $100), you need to win 52.4%
of bets to break even:
    100 / (100 + 110) = 0.476 (loss probability)
    1 - 0.476 = 0.524 (required win probability)

If our edge hypothesis shows >52.4% win rate AND is statistically
significant (p < 0.05), we have a profitable betting strategy.

Statistical Methods Used
=======================
1. Binomial Test: Tests if observed win rate differs from 50% (fair market)
2. Wilson Confidence Interval: Better than normal approximation for proportions,
   especially with small-to-medium sample sizes
3. P-value: Probability of seeing this result if null hypothesis (no edge) is true

Interpreting Results
==================
- EDGE EXISTS: Win% > 52.4% AND p-value < 0.05
- EDGE POSSIBLE: Win% > 52.4% but p-value >= 0.05 (need more data)
- NO EDGE: Win% <= 52.4% or statistically indistinguishable from chance

Usage:
    python validate_edge.py                   # Load from database
    python validate_edge.py --csv data.csv   # Load from CSV file
    python validate_edge.py --use-spread     # Use actual spread data if available
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


# Breakeven threshold at standard -110 odds
# At -110, you risk $110 to win $100
# Breakeven = 110 / (110 + 100) = 0.524 = 52.4%
# Any win rate above this is profitable long-term
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
    Filter to our target betting scenario:
    - Same conference matchups (teams know each other well)
    - One team ranked, one team unranked (asymmetric public perception)

    Why These Filters?
    =================
    1. Same Conference: Conference familiarity reduces variance. Teams have
       played each other before, game-planned specifically, and coaching
       matchups are established. This theoretically reduces the ranked
       team's advantage.

    2. Ranked vs Unranked: This creates the perception gap we're exploiting.
       The public sees "Top 15 vs Unranked" and bets the ranked team, but
       in-conference that ranking gap is often misleading.

    Args:
        df: Games DataFrame with same_conference and ranked_vs_unranked columns

    Returns:
        Filtered DataFrame containing only target scenario games
    """
    # Ensure boolean columns (CSV loading may create strings)
    if df["same_conference"].dtype != bool:
        df["same_conference"] = df["same_conference"].astype(bool)
    if df["ranked_vs_unranked"].dtype != bool:
        df["ranked_vs_unranked"] = df["ranked_vs_unranked"].astype(bool)

    # Apply both filters: conference game AND ranked vs unranked matchup
    target = df[(df["same_conference"] == True) & (df["ranked_vs_unranked"] == True)]

    return target.copy()


def identify_underdog(row: pd.Series) -> dict:
    """
    Identify which team is the underdog based on rankings.

    Underdog Identification Logic:
    =============================
    Without actual spread data, we use AP rankings as a proxy:
    - Ranked team = assumed favorite
    - Unranked team = assumed underdog

    This is imperfect but generally accurate for our target scenario.
    In ranked vs unranked games, the ranked team is favored ~95% of the time.

    When spread data is available (via --use-spread flag), we use actual
    betting lines instead of this heuristic.

    Args:
        row: DataFrame row with home_ap_rank, away_ap_rank, team names, scores

    Returns:
        Dict with underdog info, or None if both/neither teams are ranked
        {
            "underdog": "home" or "away",
            "underdog_team": team name,
            "favorite_team": team name,
            "favorite_rank": AP ranking,
            "underdog_score": final score,
            "favorite_score": final score
        }
    """
    home_ranked = pd.notna(row["home_ap_rank"])
    away_ranked = pd.notna(row["away_ap_rank"])

    # In ranked vs unranked scenario, the unranked team is the underdog
    if home_ranked and not away_ranked:
        # Home team ranked (favorite), away team unranked (underdog)
        # This is our "upset opportunity" scenario
        return {
            "underdog": "away",
            "underdog_team": row["away_team"],
            "favorite_team": row["home_team"],
            "favorite_rank": row["home_ap_rank"],
            "underdog_score": row["away_score"],
            "favorite_score": row["home_score"],
        }
    elif away_ranked and not home_ranked:
        # Away team ranked (favorite), home team unranked (underdog)
        # Road favorite scenario - historically tough for favorites
        return {
            "underdog": "home",
            "underdog_team": row["home_team"],
            "favorite_team": row["away_team"],
            "favorite_rank": row["away_ap_rank"],
            "underdog_score": row["home_score"],
            "favorite_score": row["away_score"],
        }
    else:
        # Both ranked or both unranked - doesn't fit our target scenario
        return None


def calculate_ats_result(row: pd.Series, spread: float = None) -> str:
    """
    Calculate Against The Spread (ATS) result for the underdog.

    ATS Betting Explained:
    =====================
    When betting ATS, you're betting the underdog will either:
    1. Win outright, OR
    2. Lose by LESS than the spread

    Example: Duke -7.5 vs UNC
    - If UNC loses by 7 or less, UNC "covers"
    - If UNC loses by 8+, Duke "covers"
    - The .5 eliminates pushes (ties)

    Without Spread Data:
    ===================
    When actual spread data isn't available, we use straight-up win/loss
    as a proxy. This is imperfect because:
    - Some underdogs lose but would have covered
    - Some favorites win but don't cover

    The proxy is most useful for large samples where these effects average out.

    Args:
        row: DataFrame row with game data
        spread: Actual betting spread if available (positive = underdog getting points)

    Returns:
        'cover'/'win' - Underdog covered or won outright
        'loss' - Underdog lost and didn't cover
        'push' - Exact spread (rare with .5 spreads)
    """
    underdog_info = identify_underdog(row)
    if not underdog_info:
        return None

    # Calculate actual margin from underdog's perspective
    # Positive = underdog won, Negative = underdog lost
    actual_margin = underdog_info["underdog_score"] - underdog_info["favorite_score"]

    # If we have actual spread data, calculate true ATS result
    if spread is not None:
        # Spread is expressed as "favorite -X", so underdog is +X
        # Underdog covers if they win, OR lose by less than the spread
        # Example: spread=7 means favorite -7, underdog +7
        # Underdog covers if actual_margin > -7 (lose by less than 7)
        if actual_margin > -spread:
            return "cover"
        elif actual_margin < -spread:
            return "loss"
        else:
            return "push"  # Exact spread (rare)

    # Without spread data, use straight-up result as proxy
    # This underestimates edge (some losses would be covers)
    if actual_margin > 0:
        return "win"  # Underdog won outright - definitely a cover
    elif actual_margin < 0:
        return "loss"  # Underdog lost - may or may not have covered
    else:
        return "push"  # Tie game (very rare)


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

    Why Wilson Over Normal Approximation?
    ====================================
    The normal approximation (p +/- z*sqrt(p(1-p)/n)) has problems:
    1. Can produce impossible intervals (< 0 or > 1)
    2. Inaccurate for small samples
    3. Inaccurate when p is near 0 or 1

    Wilson score interval is more accurate for:
    - Small to medium samples (n < 500)
    - Proportions near boundaries (p < 0.2 or p > 0.8)
    - Any sample size when we need accurate coverage

    Formula:
    ========
    center = (p_hat + z^2/2n) / (1 + z^2/n)
    margin = z * sqrt((p_hat(1-p_hat) + z^2/4n) / n) / (1 + z^2/n)

    Interpretation:
    ==============
    A 95% CI of [0.52, 0.62] means we're 95% confident the true
    cover rate is between 52% and 62%. If both bounds > 52.4%,
    we have strong evidence of a profitable edge.

    Args:
        successes: Number of wins/covers
        trials: Total number of bets (excluding pushes)
        confidence: Confidence level (default: 0.95 for 95% CI)

    Returns:
        Tuple of (lower_bound, upper_bound)
    """
    if trials == 0:
        return (0, 0)

    # Z-score for desired confidence level
    # 95% confidence -> z = 1.96
    z = stats.norm.ppf(1 - (1 - confidence) / 2)
    p_hat = successes / trials

    # Wilson score formula
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

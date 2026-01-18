"""
Validate the Top 5 edge finding.
"""
import pandas as pd
import numpy as np
from scipy import stats

games = pd.read_csv('backend/data/raw/games_2020_2024.csv')
target = games[(games['same_conference'] == True) & (games['ranked_vs_unranked'] == True)].copy()

def get_matchup(row):
    if pd.notna(row['home_ap_rank']):
        return {
            'favorite_rank': row['home_ap_rank'],
            'actual_margin': row['home_score'] - row['away_score'],
        }
    else:
        return {
            'favorite_rank': row['away_ap_rank'],
            'actual_margin': row['away_score'] - row['home_score'],
        }

matchups = target.apply(get_matchup, axis=1, result_type='expand')
target = pd.concat([target, matchups], axis=1)

# TOP 5 ANALYSIS (where we see the edge)
top5 = target[target['favorite_rank'] <= 5].copy()
top5['covered'] = top5['actual_margin'] < 14  # Market spread of -14

covers = int(top5['covered'].sum())
total = len(top5)
cover_pct = covers / total

print('=' * 60)
print('EDGE VALIDATION: TOP 5 RANKED vs UNRANKED CONFERENCE GAMES')
print('=' * 60)
print()
print(f'Sample Size: {total} games')
print(f'Underdog Covers: {covers}')
print(f'Cover Rate: {cover_pct:.2%}')
print(f'Breakeven: 52.40%')
print()

# Statistical tests
# Test vs 50% (fair market)
result_50 = stats.binomtest(covers, total, p=0.50, alternative='greater')
print(f'Test vs 50.0%: p-value = {result_50.pvalue:.4f}')

# Test vs 52.4% (breakeven)
result_524 = stats.binomtest(covers, total, p=0.524, alternative='greater')
print(f'Test vs 52.4%: p-value = {result_524.pvalue:.4f}')

# Confidence interval
ci = result_50.proportion_ci(confidence_level=0.95)
print(f'95% CI: {ci.low:.2%} - {ci.high:.2%}')

print()
print('-' * 60)
if cover_pct > 0.524 and result_524.pvalue < 0.05:
    print('RESULT: *** EDGE VALIDATED ***')
    print()
    print('Interpretation:')
    print('  When a Top-5 ranked team plays an unranked team from')
    print('  the same conference, and the spread is around -14,')
    print(f'  the underdog covers at {cover_pct:.1%} (>52.4% breakeven)')
    print()

    # Calculate expected profit
    bets = total
    wins = covers
    profit = wins * 100 - (bets - wins) * 110
    roi = profit / (bets * 110)
    print(f'Hypothetical ROI (at -110): {roi:.1%}')
    print(f'  {bets} bets, {wins} wins, {bets-wins} losses')
    print(f'  Net: ${profit:+,.0f} on ${bets*110:,.0f} wagered')
elif cover_pct > 0.524:
    print('RESULT: Edge exists but NOT statistically significant')
    print(f'  (p={result_524.pvalue:.3f} >= 0.05)')
else:
    print('RESULT: No edge found')
print('-' * 60)

# Additional analysis: what spread would be breakeven?
print()
print('ADDITIONAL ANALYSIS:')
print(f'Median actual margin: {top5["actual_margin"].median():.1f} pts')
print(f'Mean actual margin: {top5["actual_margin"].mean():.1f} pts')
print()

# Test different spread assumptions
print('Cover rates at different spreads:')
for spread in [10, 11, 12, 13, 14, 15, 16]:
    cov = (top5['actual_margin'] < spread).sum()
    pct = cov / total
    marker = ' <-- breakeven' if abs(pct - 0.524) < 0.02 else ''
    print(f'  Spread -{spread}: {pct:.1%}{marker}')

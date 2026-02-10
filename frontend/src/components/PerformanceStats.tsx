'use client';

import { useMemo } from 'react';
import type { BetResult, ConfidenceTier } from '@/lib/types';

interface TierStats {
  tier: string;
  total: number;
  wins: number;
  losses: number;
  pushes: number;
  winPct: number;
  unitsWon: number;
  roi: number;
}

interface PerformanceStatsProps {
  betResults: (BetResult & {
    confidence_tier?: ConfidenceTier | null;
    home_team?: string;
    away_team?: string;
    date?: string;
  })[];
  seasonPerformance: {
    total_bets: number;
    wins: number;
    losses: number;
    pushes: number;
    win_pct: number | null;
    units_wagered: number;
    units_won: number;
    roi_pct: number | null;
  } | null;
}

export function PerformanceStats({ betResults, seasonPerformance }: PerformanceStatsProps) {
  const stats = useMemo(() => {
    if (seasonPerformance) return seasonPerformance;
    // Compute from raw bet results if view not available
    const graded = betResults.filter(b => b.result && b.result !== 'pending');
    const wins = graded.filter(b => b.result === 'win').length;
    const losses = graded.filter(b => b.result === 'loss').length;
    const pushes = graded.filter(b => b.result === 'push').length;
    const unitsWon = graded.reduce((sum, b) => sum + (b.units_won ?? 0), 0);
    const unitsWagered = graded.reduce((sum, b) => sum + b.units_wagered, 0);
    return {
      total_bets: graded.length,
      wins,
      losses,
      pushes,
      win_pct: graded.length > 0 ? (wins / (wins + losses)) * 100 : null,
      units_wagered: unitsWagered,
      units_won: unitsWon,
      roi_pct: unitsWagered > 0 ? (unitsWon / unitsWagered) * 100 : null,
    };
  }, [betResults, seasonPerformance]);

  // Confidence tier breakdown
  const tierBreakdown = useMemo<TierStats[]>(() => {
    const tiers: Record<string, { wins: number; losses: number; pushes: number; unitsWon: number; unitsWagered: number }> = {};
    for (const bet of betResults) {
      if (!bet.result || bet.result === 'pending') continue;
      const tier = bet.confidence_tier || 'unknown';
      if (!tiers[tier]) tiers[tier] = { wins: 0, losses: 0, pushes: 0, unitsWon: 0, unitsWagered: 0 };
      if (bet.result === 'win') tiers[tier].wins++;
      else if (bet.result === 'loss') tiers[tier].losses++;
      else if (bet.result === 'push') tiers[tier].pushes++;
      tiers[tier].unitsWon += bet.units_won ?? 0;
      tiers[tier].unitsWagered += bet.units_wagered;
    }

    const order = ['high', 'medium', 'low', 'pass', 'unknown'];
    return order
      .filter(t => tiers[t])
      .map(t => {
        const d = tiers[t];
        const total = d.wins + d.losses + d.pushes;
        return {
          tier: t,
          total,
          wins: d.wins,
          losses: d.losses,
          pushes: d.pushes,
          winPct: d.wins + d.losses > 0 ? (d.wins / (d.wins + d.losses)) * 100 : 0,
          unitsWon: d.unitsWon,
          roi: d.unitsWagered > 0 ? (d.unitsWon / d.unitsWagered) * 100 : 0,
        };
      });
  }, [betResults]);

  // Current streak
  const streak = useMemo(() => {
    const graded = betResults
      .filter(b => b.result === 'win' || b.result === 'loss')
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    if (graded.length === 0) return { count: 0, type: null as 'W' | 'L' | null };
    const streakType = graded[0].result === 'win' ? 'W' : 'L';
    let count = 0;
    for (const bet of graded) {
      if ((bet.result === 'win' ? 'W' : 'L') === streakType) count++;
      else break;
    }
    return { count, type: streakType };
  }, [betResults]);

  // Recent picks (last 20)
  const recentPicks = useMemo(() => {
    return betResults
      .filter(b => b.result && b.result !== 'pending')
      .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      .slice(0, 20);
  }, [betResults]);

  const tierColor = (tier: string) => {
    switch (tier) {
      case 'high': return 'text-green-400';
      case 'medium': return 'text-yellow-400';
      case 'low': return 'text-orange-400';
      default: return 'text-gray-400';
    }
  };

  const resultColor = (result: string | null) => {
    switch (result) {
      case 'win': return 'text-green-400';
      case 'loss': return 'text-red-400';
      case 'push': return 'text-yellow-400';
      default: return 'text-gray-400';
    }
  };

  const hasData = stats.total_bets > 0;

  if (!hasData) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p className="text-lg mb-2">No bet results yet</p>
        <p className="text-sm">Performance data will appear here once bets are graded</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <p className="text-xs sm:text-sm text-gray-400 mb-1">Season ROI</p>
          <p className={`text-2xl sm:text-3xl font-bold ${(stats.roi_pct ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.roi_pct !== null ? `${stats.roi_pct >= 0 ? '+' : ''}${stats.roi_pct.toFixed(1)}%` : '--'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {stats.units_won >= 0 ? '+' : ''}{stats.units_won.toFixed(1)}u
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <p className="text-xs sm:text-sm text-gray-400 mb-1">Win Rate</p>
          <p className="text-2xl sm:text-3xl font-bold text-white">
            {stats.win_pct !== null ? `${stats.win_pct.toFixed(1)}%` : '--'}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            {stats.wins}W - {stats.losses}L{stats.pushes > 0 ? ` - ${stats.pushes}P` : ''}
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <p className="text-xs sm:text-sm text-gray-400 mb-1">Total Bets</p>
          <p className="text-2xl sm:text-3xl font-bold text-white">{stats.total_bets}</p>
          <p className="text-xs text-gray-500 mt-1">
            {stats.units_wagered.toFixed(1)}u wagered
          </p>
        </div>

        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <p className="text-xs sm:text-sm text-gray-400 mb-1">Current Streak</p>
          <p className={`text-2xl sm:text-3xl font-bold ${streak.type === 'W' ? 'text-green-400' : streak.type === 'L' ? 'text-red-400' : 'text-gray-400'}`}>
            {streak.count > 0 ? `${streak.count}${streak.type}` : '--'}
          </p>
        </div>
      </div>

      {/* Confidence Tier Breakdown */}
      {tierBreakdown.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Performance by Confidence Tier</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-gray-400 border-b border-gray-800">
                  <th className="text-left py-2 pr-4">Tier</th>
                  <th className="text-right py-2 px-2">Bets</th>
                  <th className="text-right py-2 px-2">Record</th>
                  <th className="text-right py-2 px-2">Win %</th>
                  <th className="text-right py-2 px-2">Units</th>
                  <th className="text-right py-2 pl-2">ROI</th>
                </tr>
              </thead>
              <tbody>
                {tierBreakdown.map(t => (
                  <tr key={t.tier} className="border-b border-gray-800/50">
                    <td className={`py-2.5 pr-4 font-medium capitalize ${tierColor(t.tier)}`}>
                      {t.tier}
                    </td>
                    <td className="text-right py-2.5 px-2 text-gray-300">{t.total}</td>
                    <td className="text-right py-2.5 px-2 text-gray-300">
                      {t.wins}-{t.losses}{t.pushes > 0 ? `-${t.pushes}` : ''}
                    </td>
                    <td className="text-right py-2.5 px-2 text-gray-300">
                      {t.winPct.toFixed(1)}%
                    </td>
                    <td className={`text-right py-2.5 px-2 ${t.unitsWon >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {t.unitsWon >= 0 ? '+' : ''}{t.unitsWon.toFixed(1)}
                    </td>
                    <td className={`text-right py-2.5 pl-2 ${t.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {t.roi >= 0 ? '+' : ''}{t.roi.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Picks */}
      {recentPicks.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
          <h2 className="text-lg font-semibold text-white mb-4">Recent Picks</h2>
          <div className="space-y-2">
            {recentPicks.map(pick => (
              <div key={pick.id} className="flex items-center justify-between py-2 border-b border-gray-800/50 last:border-0">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`text-xs font-bold w-10 text-center uppercase ${resultColor(pick.result)}`}>
                    {pick.result}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm text-gray-300 truncate">
                      {pick.home_team && pick.away_team
                        ? `${pick.away_team} @ ${pick.home_team}`
                        : `Game ${pick.game_id?.slice(0, 8)}`}
                    </p>
                    <p className="text-xs text-gray-500">
                      {pick.bet_type.toUpperCase()} {pick.side} {pick.spread_at_bet !== null ? `(${pick.spread_at_bet > 0 ? '+' : ''}${pick.spread_at_bet})` : ''}
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0 ml-2">
                  <p className={`text-sm font-medium ${(pick.units_won ?? 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(pick.units_won ?? 0) >= 0 ? '+' : ''}{(pick.units_won ?? 0).toFixed(1)}u
                  </p>
                  {pick.confidence_tier && (
                    <p className={`text-xs capitalize ${tierColor(pick.confidence_tier)}`}>
                      {pick.confidence_tier}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

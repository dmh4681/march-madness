'use client';

import Link from 'next/link';
import type { TodayGame } from '@/lib/types';
import { ConfidenceBadge } from './ConfidenceBadge';
import { formatSpread } from '@/lib/api';

interface PicksListProps {
  games: TodayGame[];
  title?: string;
}

export function PicksList({ games, title = "Today's Top Picks" }: PicksListProps) {
  // Filter to only games with predictions and sort by edge
  const picks = games
    .filter(
      (g) =>
        g.confidence_tier &&
        g.confidence_tier !== 'pass' &&
        g.recommended_bet &&
        g.recommended_bet !== 'pass'
    )
    .sort((a, b) => (b.edge_pct || 0) - (a.edge_pct || 0));

  if (picks.length === 0) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <h2 className="text-lg font-semibold text-white mb-4">{title}</h2>
        <p className="text-gray-400 text-center py-4">
          No picks for today. Check back when games are analyzed.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">{title}</h2>
      <div className="space-y-3">
        {picks.map((game) => (
          <PickCard key={game.id} game={game} />
        ))}
      </div>
    </div>
  );
}

function PickCard({ game }: { game: TodayGame }) {
  const isHomePick = game.recommended_bet?.includes('home');
  const pickedTeam = isHomePick ? game.home_team : game.away_team;
  const spread = isHomePick ? game.home_spread : game.home_spread ? -game.home_spread : null;
  const isSpreadBet = game.recommended_bet?.includes('spread');

  return (
    <Link href={`/games/${game.id}`}>
      <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg hover:bg-gray-800 transition-colors">
        <div className="flex items-center gap-3">
          <ConfidenceBadge tier={game.confidence_tier} />
          <div>
            <div className="font-medium text-white">
              {pickedTeam} {isSpreadBet ? formatSpread(spread) : 'ML'}
            </div>
            <div className="text-sm text-gray-400">
              vs {isHomePick ? game.away_team : game.home_team}
            </div>
          </div>
        </div>
        <div className="text-right">
          {game.edge_pct && game.edge_pct > 0 && (
            <div className="text-green-400 font-medium">
              +{game.edge_pct.toFixed(1)}%
            </div>
          )}
          <div className="text-xs text-gray-500">edge</div>
        </div>
      </div>
    </Link>
  );
}

// Stats summary component
interface StatsCardProps {
  seasonRoi: number;
  winRate: number;
  totalBets: number;
  streak: { count: number; type: 'W' | 'L' } | null;
}

export function StatsCard({ seasonRoi, winRate, totalBets, streak }: StatsCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h2 className="text-lg font-semibold text-white mb-4">Season Performance</h2>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-2xl font-bold text-white">
            <span className={seasonRoi >= 0 ? 'text-green-400' : 'text-red-400'}>
              {seasonRoi >= 0 ? '+' : ''}
              {seasonRoi.toFixed(1)}%
            </span>
          </div>
          <div className="text-sm text-gray-400">ROI</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            {winRate.toFixed(1)}%
          </div>
          <div className="text-sm text-gray-400">Win Rate</div>
        </div>
        <div>
          <div className="text-2xl font-bold text-white">{totalBets}</div>
          <div className="text-sm text-gray-400">Total Bets</div>
        </div>
        <div>
          {streak ? (
            <>
              <div
                className={`text-2xl font-bold ${
                  streak.type === 'W' ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {streak.count}
                {streak.type}
              </div>
              <div className="text-sm text-gray-400">Streak</div>
            </>
          ) : (
            <>
              <div className="text-2xl font-bold text-gray-500">-</div>
              <div className="text-sm text-gray-400">Streak</div>
            </>
          )}
        </div>
      </div>
      <Link
        href="/performance"
        className="mt-4 block text-center text-sm text-blue-400 hover:text-blue-300"
      >
        View detailed stats →
      </Link>
    </div>
  );
}

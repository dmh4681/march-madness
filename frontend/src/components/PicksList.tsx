'use client';

import { useId } from 'react';
import Link from 'next/link';
import type { TodayGame } from '@/lib/types';
import { ConfidenceBadge, getConfidenceDescription } from './ConfidenceBadge';
import { formatSpread } from '@/lib/api';

interface PicksListProps {
  games: TodayGame[];
  title?: string;
}

export function PicksList({ games, title = "Today's Top Picks" }: PicksListProps) {
  const headingId = useId();

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
      <section
        className="bg-gray-900 border border-gray-800 rounded-lg p-6"
        aria-labelledby={headingId}
      >
        <h2 id={headingId} className="text-lg font-semibold text-white mb-4">{title}</h2>
        <p className="text-gray-400 text-center py-4" role="status">
          No picks for today. Check back when games are analyzed.
        </p>
      </section>
    );
  }

  return (
    <section
      className="bg-gray-900 border border-gray-800 rounded-lg p-6"
      aria-labelledby={headingId}
    >
      <h2 id={headingId} className="text-lg font-semibold text-white mb-4">{title}</h2>
      <nav aria-label="Betting picks navigation">
        <ul className="space-y-3" role="list">
          {picks.map((game, index) => (
            <li key={game.id}>
              <PickCard game={game} position={index + 1} total={picks.length} />
            </li>
          ))}
        </ul>
      </nav>
    </section>
  );
}

interface PickCardProps {
  game: TodayGame;
  position: number;
  total: number;
}

function PickCard({ game, position, total }: PickCardProps) {
  const isHomePick = game.recommended_bet?.includes('home');
  const pickedTeam = isHomePick ? game.home_team : game.away_team;
  const opponent = isHomePick ? game.away_team : game.home_team;
  const spread = isHomePick ? game.home_spread : game.home_spread ? -game.home_spread : null;
  const isSpreadBet = game.recommended_bet?.includes('spread');
  const confidenceDescription = getConfidenceDescription(game.confidence_tier);
  const betType = isSpreadBet ? `spread ${formatSpread(spread)}` : 'moneyline';

  // Build comprehensive accessible label
  const accessibleLabel = `Pick ${position} of ${total}: ${pickedTeam} ${betType} versus ${opponent}. ${confidenceDescription}${
    game.edge_pct && game.edge_pct > 0 ? `, ${game.edge_pct.toFixed(1)} percent edge` : ''
  }`;

  return (
    <Link
      href={`/games/${game.id}`}
      aria-label={accessibleLabel}
      className="block focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded-lg"
    >
      <div className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg hover:bg-gray-800 transition-colors">
        <div className="flex items-center gap-3">
          <ConfidenceBadge tier={game.confidence_tier} />
          <div>
            <div className="font-medium text-white flex items-center gap-2">
              <span>{pickedTeam} {isSpreadBet ? formatSpread(spread) : 'ML'}</span>
              {/* AI provider indicators */}
              <span className="flex items-center gap-0.5">
                {game.has_claude_analysis && (
                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500" title="Claude analysis" />
                )}
                {game.has_grok_analysis && (
                  <span className="w-1.5 h-1.5 rounded-full bg-orange-500" title="Grok analysis" />
                )}
              </span>
            </div>
            <div className="text-sm text-gray-400">
              vs {opponent}
            </div>
          </div>
        </div>
        <div className="text-right" aria-hidden="true">
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
  const headingId = `stats-heading-${Math.random().toString(36).slice(2, 9)}`;
  const roiLabel = `Return on investment: ${seasonRoi >= 0 ? 'positive ' : 'negative '}${Math.abs(seasonRoi).toFixed(1)} percent`;
  const streakLabel = streak
    ? `Current streak: ${streak.count} ${streak.type === 'W' ? 'wins' : 'losses'}`
    : 'No current streak';

  return (
    <section
      className="bg-gray-900 border border-gray-800 rounded-lg p-6"
      aria-labelledby={headingId}
    >
      <h2 id={headingId} className="text-lg font-semibold text-white mb-4">Season Performance</h2>
      <dl className="grid grid-cols-2 gap-4">
        <div>
          <dd className="text-2xl font-bold text-white">
            <span
              className={seasonRoi >= 0 ? 'text-green-400' : 'text-red-400'}
              aria-label={roiLabel}
            >
              {seasonRoi >= 0 ? '+' : ''}
              {seasonRoi.toFixed(1)}%
            </span>
          </dd>
          <dt className="text-sm text-gray-400">ROI</dt>
        </div>
        <div>
          <dd
            className="text-2xl font-bold text-white"
            aria-label={`Win rate: ${winRate.toFixed(1)} percent`}
          >
            {winRate.toFixed(1)}%
          </dd>
          <dt className="text-sm text-gray-400">Win Rate</dt>
        </div>
        <div>
          <dd
            className="text-2xl font-bold text-white"
            aria-label={`Total bets: ${totalBets}`}
          >
            {totalBets}
          </dd>
          <dt className="text-sm text-gray-400">Total Bets</dt>
        </div>
        <div>
          {streak ? (
            <>
              <dd
                className={`text-2xl font-bold ${
                  streak.type === 'W' ? 'text-green-400' : 'text-red-400'
                }`}
                aria-label={streakLabel}
              >
                {streak.count}
                {streak.type}
              </dd>
              <dt className="text-sm text-gray-400">Streak</dt>
            </>
          ) : (
            <>
              <dd className="text-2xl font-bold text-gray-500" aria-label={streakLabel}>-</dd>
              <dt className="text-sm text-gray-400">Streak</dt>
            </>
          )}
        </div>
      </dl>
      <Link
        href="/performance"
        className="mt-4 block text-center text-sm text-blue-400 hover:text-blue-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded"
        aria-label="View detailed performance statistics"
      >
        View detailed stats →
      </Link>
    </section>
  );
}

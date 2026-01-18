'use client';

import Link from 'next/link';
import { format } from 'date-fns';
import type { TodayGame } from '@/lib/types';
import { ConfidenceBadge } from './ConfidenceBadge';
import { formatSpread, formatMoneyline, formatProbability } from '@/lib/api';

interface GameCardProps {
  game: TodayGame;
  showPrediction?: boolean;
}

export function GameCard({ game, showPrediction = true }: GameCardProps) {
  const tipTime = game.tip_time
    ? format(new Date(game.tip_time), 'h:mm a')
    : 'TBD';

  const isRankedMatchup = game.home_rank || game.away_rank;
  const isConferenceGame = game.is_conference_game;

  return (
    <Link href={`/games/${game.id}`}>
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors cursor-pointer">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm text-gray-400">{tipTime}</span>
          <div className="flex items-center gap-2">
            {isConferenceGame && (
              <span className="text-xs px-2 py-0.5 bg-blue-500/20 text-blue-400 rounded">
                CONF
              </span>
            )}
            {isRankedMatchup && (
              <span className="text-xs px-2 py-0.5 bg-purple-500/20 text-purple-400 rounded">
                RANKED
              </span>
            )}
          </div>
        </div>

        {/* Teams */}
        <div className="space-y-2 mb-4">
          {/* Away Team */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {game.away_rank && (
                <span className="text-xs font-bold text-yellow-500">
                  #{game.away_rank}
                </span>
              )}
              <span className="font-medium text-white">{game.away_team}</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-gray-400 w-12 text-right">
                {formatSpread(game.home_spread ? -game.home_spread : null)}
              </span>
              <span className="text-gray-500 w-14 text-right">
                {formatMoneyline(game.away_ml)}
              </span>
            </div>
          </div>

          {/* Home Team */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {game.home_rank && (
                <span className="text-xs font-bold text-yellow-500">
                  #{game.home_rank}
                </span>
              )}
              <span className="font-medium text-white">{game.home_team}</span>
              <span className="text-xs text-gray-500">(H)</span>
            </div>
            <div className="flex items-center gap-3 text-sm">
              <span className="text-gray-400 w-12 text-right">
                {formatSpread(game.home_spread)}
              </span>
              <span className="text-gray-500 w-14 text-right">
                {formatMoneyline(game.home_ml)}
              </span>
            </div>
          </div>
        </div>

        {/* Total */}
        {game.over_under && (
          <div className="flex items-center justify-between text-sm text-gray-400 mb-3 pb-3 border-b border-gray-800">
            <span>Total</span>
            <span>O/U {game.over_under}</span>
          </div>
        )}

        {/* Prediction */}
        {showPrediction && game.predicted_home_cover_prob !== null && (
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <ConfidenceBadge tier={game.confidence_tier} />
              {game.recommended_bet && game.recommended_bet !== 'pass' && (
                <span className="text-sm font-medium text-white">
                  {game.recommended_bet.includes('home')
                    ? game.home_team
                    : game.away_team}{' '}
                  {game.recommended_bet.includes('spread') ? formatSpread(
                    game.recommended_bet.includes('home')
                      ? game.home_spread
                      : game.home_spread ? -game.home_spread : null
                  ) : 'ML'}
                </span>
              )}
            </div>
            {game.edge_pct && game.edge_pct > 0 && (
              <span className="text-sm text-green-400">
                +{game.edge_pct.toFixed(1)}% edge
              </span>
            )}
          </div>
        )}

        {/* No prediction yet */}
        {showPrediction && game.predicted_home_cover_prob === null && (
          <div className="text-sm text-gray-500 italic">
            Analysis pending...
          </div>
        )}
      </div>
    </Link>
  );
}

// Compact version for sidebar/lists
export function GameCardCompact({ game }: { game: TodayGame }) {
  return (
    <Link href={`/games/${game.id}`}>
      <div className="flex items-center justify-between py-2 px-3 hover:bg-gray-800/50 rounded transition-colors">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 text-sm">
            {game.away_rank && (
              <span className="text-yellow-500 text-xs">#{game.away_rank}</span>
            )}
            <span className="truncate text-gray-300">{game.away_team}</span>
            <span className="text-gray-600">@</span>
            {game.home_rank && (
              <span className="text-yellow-500 text-xs">#{game.home_rank}</span>
            )}
            <span className="truncate text-gray-300">{game.home_team}</span>
          </div>
        </div>
        {game.confidence_tier && game.confidence_tier !== 'pass' && (
          <ConfidenceBadge tier={game.confidence_tier} showLabel={false} />
        )}
      </div>
    </Link>
  );
}

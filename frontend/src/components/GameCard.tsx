'use client';

import { useState, useId, useEffect, useRef } from 'react';
import Link from 'next/link';
import { format } from 'date-fns';
import type { TodayGame } from '@/lib/types';
import { ConfidenceBadge, getConfidenceDescription } from './ConfidenceBadge';
import { formatSpread, formatMoneyline } from '@/lib/api';
import { GameCardSkeleton, Skeleton } from './ui/skeleton';
import { useAnnounce } from './ui/LiveRegion';
import { useGameAnalytics } from '@/hooks/useGameAnalytics';
import { cn } from '@/lib/utils';

interface GameCardProps {
  game: TodayGame;
  showPrediction?: boolean;
}

export function GameCard({ game, showPrediction = true }: GameCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const predictionId = useId();
  const oddsId = useId();
  const { announce } = useAnnounce();

  // Track previous odds to detect changes and announce to screen readers
  const prevOddsRef = useRef({
    spread: game.home_spread,
    homeML: game.home_ml,
    awayML: game.away_ml,
    overUnder: game.over_under
  });

  // Announce odds changes to screen readers
  useEffect(() => {
    const prev = prevOddsRef.current;
    const changes: string[] = [];

    if (prev.spread !== game.home_spread && game.home_spread !== null) {
      changes.push(`spread moved to ${formatSpread(game.home_spread)}`);
    }
    if (prev.homeML !== game.home_ml && game.home_ml !== null) {
      changes.push(`${game.home_team} moneyline now ${formatMoneyline(game.home_ml)}`);
    }
    if (prev.awayML !== game.away_ml && game.away_ml !== null) {
      changes.push(`${game.away_team} moneyline now ${formatMoneyline(game.away_ml)}`);
    }
    if (prev.overUnder !== game.over_under && game.over_under !== null) {
      changes.push(`total moved to ${game.over_under}`);
    }

    if (changes.length > 0) {
      announce(`${game.away_team} at ${game.home_team}: ${changes.join(', ')}`);
    }

    // Update ref with current values
    prevOddsRef.current = {
      spread: game.home_spread,
      homeML: game.home_ml,
      awayML: game.away_ml,
      overUnder: game.over_under
    };
  }, [game.home_spread, game.home_ml, game.away_ml, game.over_under, game.away_team, game.home_team, announce]);

  const tipTime = game.tip_time
    ? format(new Date(game.tip_time), 'h:mm a')
    : 'TBD';

  const isRankedMatchup = game.home_rank || game.away_rank;
  const isConferenceGame = game.is_conference_game;

  // Build accessible description for the game card
  const gameDescription = `${game.away_team} at ${game.home_team}, ${tipTime}${
    isRankedMatchup ? ', ranked matchup' : ''
  }${isConferenceGame ? ', conference game' : ''}`;

  return (
    <article
      className="bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-700 transition-colors"
      aria-label={gameDescription}
    >
      {/* Main card content - links to detail page */}
      <Link
        href={`/games/${game.id}`}
        className="block p-3 sm:p-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded-t-lg"
        aria-describedby={showPrediction ? predictionId : undefined}
      >
        {/* Header - touch-friendly badges */}
        <div className="flex items-center justify-between mb-3">
          <time className="text-sm text-gray-400" dateTime={game.tip_time || undefined}>
            {tipTime}
          </time>
          <div className="flex items-center gap-2" role="list" aria-label="Game tags">
            {isConferenceGame && (
              <span
                role="listitem"
                className="text-xs px-2.5 py-1 min-h-[28px] flex items-center bg-blue-500/20 text-blue-400 rounded sm:px-2 sm:py-0.5 sm:min-h-0"
                aria-label="Conference game"
              >
                CONF
              </span>
            )}
            {isRankedMatchup && (
              <span
                role="listitem"
                className="text-xs px-2.5 py-1 min-h-[28px] flex items-center bg-purple-500/20 text-purple-400 rounded sm:px-2 sm:py-0.5 sm:min-h-0"
                aria-label="Ranked matchup"
              >
                RANKED
              </span>
            )}
          </div>
        </div>

        {/* Teams - larger touch targets on mobile */}
        <div className="space-y-3 sm:space-y-2 mb-4" role="list" aria-label="Teams and betting lines">
          {/* Away Team */}
          <div className="flex items-center justify-between min-h-[44px] sm:min-h-0" role="listitem">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {game.away_rank && (
                <span className="text-xs font-bold text-yellow-500 shrink-0" aria-label={`Ranked number ${game.away_rank}`}>
                  #{game.away_rank}
                </span>
              )}
              <span className="font-medium text-white truncate">{game.away_team}</span>
            </div>
            <div className="flex items-center gap-2 sm:gap-3 text-sm shrink-0 ml-2" id={`${oddsId}-away`}>
              <span
                className="text-gray-400 w-12 text-right"
                aria-label={`Spread: ${formatSpread(game.home_spread ? -game.home_spread : null)}`}
              >
                {formatSpread(game.home_spread ? -game.home_spread : null)}
              </span>
              <span
                className="text-gray-500 w-14 text-right hidden sm:block"
                aria-label={`Moneyline: ${formatMoneyline(game.away_ml)}`}
              >
                {formatMoneyline(game.away_ml)}
              </span>
            </div>
          </div>

          {/* Home Team */}
          <div className="flex items-center justify-between min-h-[44px] sm:min-h-0" role="listitem">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              {game.home_rank && (
                <span className="text-xs font-bold text-yellow-500 shrink-0" aria-label={`Ranked number ${game.home_rank}`}>
                  #{game.home_rank}
                </span>
              )}
              <span className="font-medium text-white truncate">{game.home_team}</span>
              <span className="text-xs text-gray-500 shrink-0" aria-label="Home team">(H)</span>
            </div>
            <div className="flex items-center gap-2 sm:gap-3 text-sm shrink-0 ml-2" id={`${oddsId}-home`}>
              <span
                className="text-gray-400 w-12 text-right"
                aria-label={`Spread: ${formatSpread(game.home_spread)}`}
              >
                {formatSpread(game.home_spread)}
              </span>
              <span
                className="text-gray-500 w-14 text-right hidden sm:block"
                aria-label={`Moneyline: ${formatMoneyline(game.home_ml)}`}
              >
                {formatMoneyline(game.home_ml)}
              </span>
            </div>
          </div>
        </div>

        {/* Total - hidden on mobile by default, shown when expanded */}
        <div className={cn(
          "flex items-center justify-between text-sm text-gray-400 mb-3 pb-3 border-b border-gray-800",
          !isExpanded && "hidden sm:flex",
          isExpanded && "flex"
        )}>
          <span>Total</span>
          <span>O/U {game.over_under || 'N/A'}</span>
        </div>

        {/* Prediction - touch-friendly */}
        {showPrediction && game.predicted_home_cover_prob !== null && (
          <div
            id={predictionId}
            role="region"
            aria-label="Betting prediction"
            className="flex items-center justify-between flex-wrap gap-2 min-h-[44px] sm:min-h-0"
          >
            <div className="flex items-center gap-2">
              <ConfidenceBadge tier={game.confidence_tier} size="touch" />
              {game.recommended_bet && game.recommended_bet !== 'pass' && (
                <span
                  className="text-sm font-medium text-white truncate max-w-[150px] sm:max-w-none"
                  aria-label={`Recommended bet: ${
                    game.recommended_bet.includes('home') ? game.home_team : game.away_team
                  } ${game.recommended_bet.includes('spread') ? 'spread' : 'moneyline'}`}
                >
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
              <span
                className="text-sm text-green-400 shrink-0"
                aria-label={`${game.edge_pct.toFixed(1)} percent edge`}
              >
                +{game.edge_pct.toFixed(1)}% edge
              </span>
            )}
          </div>
        )}

        {/* No prediction yet */}
        {showPrediction && game.predicted_home_cover_prob === null && (
          <div
            id={predictionId}
            role="status"
            aria-live="polite"
            className="text-sm text-gray-500 italic min-h-[44px] sm:min-h-0 flex items-center"
          >
            Analysis pending...
          </div>
        )}
      </Link>

      {/* Mobile expand button - shows moneylines and total when tapped */}
      <button
        type="button"
        onClick={(e) => {
          e.preventDefault();
          setIsExpanded(!isExpanded);
        }}
        className="w-full sm:hidden flex items-center justify-center gap-1 py-3 px-4 border-t border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors min-h-[44px]"
        aria-expanded={isExpanded}
        aria-label={isExpanded ? 'Show less details' : 'Show more details'}
      >
        <span className="text-xs">{isExpanded ? 'Less' : 'More'}</span>
        <svg
          className={cn(
            "w-4 h-4 transition-transform",
            isExpanded && "rotate-180"
          )}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Expanded mobile details */}
      {isExpanded && (
        <div className="sm:hidden px-4 pb-4 border-t border-gray-800 pt-3 space-y-3">
          {/* Moneylines */}
          <div className="flex justify-between items-center text-sm">
            <span className="text-gray-400">Moneylines</span>
            <div className="flex gap-4">
              <span className="text-gray-300">
                {game.away_team.split(' ').pop()}: {formatMoneyline(game.away_ml)}
              </span>
              <span className="text-gray-300">
                {game.home_team.split(' ').pop()}: {formatMoneyline(game.home_ml)}
              </span>
            </div>
          </div>

          {/* Conferences */}
          {(game.home_conference || game.away_conference) && (
            <div className="flex justify-between items-center text-sm">
              <span className="text-gray-400">Conferences</span>
              <span className="text-gray-300">
                {game.away_conference || 'N/A'} vs {game.home_conference || 'N/A'}
              </span>
            </div>
          )}
        </div>
      )}
    </article>
  );
}

// Analytics section component that loads data lazily
function AnalyticsSection({ gameId }: { gameId: string }) {
  const { analytics, isLoading, error, loadAnalytics, hasLoaded } = useGameAnalytics(gameId);
  const [isOpen, setIsOpen] = useState(false);

  const handleToggle = () => {
    if (!hasLoaded && !isOpen) {
      loadAnalytics();
    }
    setIsOpen(!isOpen);
  };

  return (
    <div className="border-t border-gray-800">
      <button
        type="button"
        onClick={handleToggle}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-400 hover:text-white hover:bg-gray-800/50 transition-colors"
        aria-expanded={isOpen}
        aria-label={isOpen ? 'Hide advanced analytics' : 'Show advanced analytics'}
      >
        <span className="flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          Advanced Analytics
        </span>
        <svg
          className={cn(
            "w-4 h-4 transition-transform",
            isOpen && "rotate-180"
          )}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 space-y-4">
          {isLoading && (
            <div className="space-y-2">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-5/6" />
            </div>
          )}

          {error && (
            <p className="text-sm text-red-400">{error}</p>
          )}

          {analytics && !isLoading && (
            <div className="space-y-4">
              {/* KenPom Data */}
              {(analytics.home_kenpom || analytics.away_kenpom) && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    KenPom Ratings
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="space-y-1">
                      <p className="text-gray-500 text-xs">{analytics.away_team}</p>
                      {analytics.away_kenpom ? (
                        <>
                          <p className="text-white">
                            #{analytics.away_kenpom.rank} ({analytics.away_kenpom.adj_efficiency_margin?.toFixed(1) || 'N/A'} AdjEM)
                          </p>
                          <p className="text-gray-400 text-xs">
                            O: {analytics.away_kenpom.adj_offense?.toFixed(1)} | D: {analytics.away_kenpom.adj_defense?.toFixed(1)}
                          </p>
                        </>
                      ) : (
                        <p className="text-gray-500 italic">No data</p>
                      )}
                    </div>
                    <div className="space-y-1">
                      <p className="text-gray-500 text-xs">{analytics.home_team}</p>
                      {analytics.home_kenpom ? (
                        <>
                          <p className="text-white">
                            #{analytics.home_kenpom.rank} ({analytics.home_kenpom.adj_efficiency_margin?.toFixed(1) || 'N/A'} AdjEM)
                          </p>
                          <p className="text-gray-400 text-xs">
                            O: {analytics.home_kenpom.adj_offense?.toFixed(1)} | D: {analytics.home_kenpom.adj_defense?.toFixed(1)}
                          </p>
                        </>
                      ) : (
                        <p className="text-gray-500 italic">No data</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* Haslametrics Data */}
              {(analytics.home_haslametrics || analytics.away_haslametrics) && (
                <div>
                  <h4 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">
                    Haslametrics
                  </h4>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="space-y-1">
                      <p className="text-gray-500 text-xs">{analytics.away_team}</p>
                      {analytics.away_haslametrics ? (
                        <>
                          <p className="text-white">
                            #{analytics.away_haslametrics.rank} ({analytics.away_haslametrics.all_play_pct?.toFixed(1)}% All-Play)
                          </p>
                          <p className="text-gray-400 text-xs">
                            Momentum: {analytics.away_haslametrics.momentum_overall?.toFixed(1) || 'N/A'}
                          </p>
                        </>
                      ) : (
                        <p className="text-gray-500 italic">No data</p>
                      )}
                    </div>
                    <div className="space-y-1">
                      <p className="text-gray-500 text-xs">{analytics.home_team}</p>
                      {analytics.home_haslametrics ? (
                        <>
                          <p className="text-white">
                            #{analytics.home_haslametrics.rank} ({analytics.home_haslametrics.all_play_pct?.toFixed(1)}% All-Play)
                          </p>
                          <p className="text-gray-400 text-xs">
                            Momentum: {analytics.home_haslametrics.momentum_overall?.toFixed(1) || 'N/A'}
                          </p>
                        </>
                      ) : (
                        <p className="text-gray-500 italic">No data</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* No analytics available */}
              {!analytics.home_kenpom && !analytics.away_kenpom && !analytics.home_haslametrics && !analytics.away_haslametrics && (
                <p className="text-sm text-gray-500 italic">No advanced analytics available for this game.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Extended GameCard with analytics section
export function GameCardWithAnalytics({ game, showPrediction = true }: GameCardProps) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg hover:border-gray-700 transition-colors">
      <GameCard game={game} showPrediction={showPrediction} />
      <AnalyticsSection gameId={game.id} />
    </div>
  );
}

// Compact version for sidebar/lists
export function GameCardCompact({ game }: { game: TodayGame }) {
  const confidenceDescription = getConfidenceDescription(game.confidence_tier);
  const gameLabel = `${game.away_team} at ${game.home_team}${
    game.confidence_tier && game.confidence_tier !== 'pass'
      ? `, ${confidenceDescription}`
      : ''
  }`;

  return (
    <Link
      href={`/games/${game.id}`}
      className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded"
      aria-label={gameLabel}
    >
      <div className="flex items-center justify-between py-2 px-3 hover:bg-gray-800/50 rounded transition-colors">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1 text-sm">
            {game.away_rank && (
              <span className="text-yellow-500 text-xs" aria-label={`Ranked ${game.away_rank}`}>
                #{game.away_rank}
              </span>
            )}
            <span className="truncate text-gray-300">{game.away_team}</span>
            <span className="text-gray-600" aria-hidden="true">@</span>
            {game.home_rank && (
              <span className="text-yellow-500 text-xs" aria-label={`Ranked ${game.home_rank}`}>
                #{game.home_rank}
              </span>
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

// Compact skeleton for sidebar/lists
export function GameCardCompactSkeleton() {
  return (
    <div className="flex items-center justify-between py-2 px-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1">
          <Skeleton className="h-4 w-20" />
          <Skeleton className="h-4 w-4" />
          <Skeleton className="h-4 w-24" />
        </div>
      </div>
      <Skeleton className="h-5 w-12 rounded-full" />
    </div>
  );
}

// Re-export skeleton for convenience
export { GameCardSkeleton };

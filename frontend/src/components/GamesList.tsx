'use client';

import { useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import { GameCard, GameCardSkeleton } from '@/components/GameCard';
import { useInfiniteGames } from '@/hooks/useInfiniteGames';
import { GamesListErrorBoundary } from '@/components/ui/ErrorBoundary';
import type { TodayGame } from '@/lib/types';

/**
 * Parse a date string (YYYY-MM-DD) as a local date, not UTC.
 * This prevents the off-by-one-day issue when displaying dates.
 */
function parseLocalDate(dateStr: string): Date {
  // Add noon time to prevent timezone shift issues
  // "2026-01-22" -> "2026-01-22T12:00:00" (local time)
  return new Date(dateStr + 'T12:00:00');
}

interface GamesListProps {
  initialGames?: TodayGame[];
  days?: number;
}

// Group games by date for display
function groupGamesByDate(games: TodayGame[]): Record<string, TodayGame[]> {
  return games.reduce((acc, game) => {
    // Handle undefined/null dates - use 'Unknown' as fallback
    const dateKey = game.date ? game.date.split('T')[0] : 'Unknown';
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(game);
    return acc;
  }, {} as Record<string, TodayGame[]>);
}

// Skeleton loader for a date group
function DateGroupSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div>
      {/* Date header skeleton */}
      <div className="mb-3 sm:mb-4 border-b border-gray-800 pb-2 sticky top-[60px] sm:top-[72px] bg-black z-10 -mx-3 px-3 sm:mx-0 sm:px-0">
        <div className="h-5 sm:h-6 w-48 bg-gray-800 rounded animate-pulse" />
      </div>
      {/* Game cards skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
        {Array.from({ length: count }).map((_, i) => (
          <GameCardSkeleton key={i} />
        ))}
      </div>
    </div>
  );
}

function GamesListContent({ initialGames = [], days = 7 }: GamesListProps) {
  const {
    games,
    isLoading,
    isLoadingMore,
    hasMore,
    error,
    loadMore,
    refresh,
    totalGames,
  } = useInfiniteGames({ days, initialData: initialGames });

  const gamesByDate = useMemo(() => groupGamesByDate(games), [games]);
  const highConfidenceCount = useMemo(
    () => games.filter(g => g.confidence_tier === 'high').length,
    [games]
  );

  // Initial loading state
  if (isLoading) {
    return (
      <div className="space-y-6 sm:space-y-8">
        <DateGroupSkeleton count={4} />
        <DateGroupSkeleton count={3} />
      </div>
    );
  }

  // Error state
  if (error && games.length === 0) {
    return (
      <div className="text-center py-8 sm:py-12">
        <p className="text-red-400 mb-4">{error}</p>
        <button
          onClick={refresh}
          className="px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // Empty state
  if (games.length === 0) {
    return (
      <div className="text-center py-8 sm:py-12 text-gray-400">
        <p className="text-base sm:text-lg mb-2">No upcoming games found</p>
        <p className="text-sm">Check back later for new matchups</p>
      </div>
    );
  }

  return (
    <>
      {/* Page stats */}
      <div className="mb-4 sm:mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1 sm:mb-2">Upcoming Games</h1>
          <p className="text-sm sm:text-base text-gray-400">
            Showing {games.length} of {totalGames} games over the next {days} days
            {highConfidenceCount > 0 && (
              <span className="ml-2 text-green-400">
                ({highConfidenceCount} high confidence)
              </span>
            )}
          </p>
        </div>
        <button
          onClick={refresh}
          className="shrink-0 px-3 py-2 text-sm bg-gray-800 text-gray-300 rounded hover:bg-gray-700 hover:text-white transition-colors flex items-center gap-2"
          aria-label="Refresh games list"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          <span className="hidden sm:inline">Refresh</span>
        </button>
      </div>

      {/* Games by Date */}
      <div className="space-y-6 sm:space-y-8">
        {Object.entries(gamesByDate).map(([dateStr, dateGames]) => (
          <div key={dateStr}>
            <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4 border-b border-gray-800 pb-2 sticky top-[60px] sm:top-[72px] bg-black z-10 -mx-3 px-3 sm:mx-0 sm:px-0">
              {/* Short date format on mobile, full on desktop */}
              {dateStr === 'Unknown' ? (
                <span>Unknown Date</span>
              ) : (
                <>
                  <span className="sm:hidden">{format(parseLocalDate(dateStr), 'EEE, MMM d')}</span>
                  <span className="hidden sm:inline">{format(parseLocalDate(dateStr), 'EEEE, MMMM d, yyyy')}</span>
                </>
              )}
              <span className="text-sm font-normal text-gray-400 ml-2">
                ({dateGames.length} {dateGames.length === 1 ? 'game' : 'games'})
              </span>
            </h2>
            {/* Single column on mobile, responsive grid on larger screens */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
              {dateGames.map((game) => (
                <GameCard key={game.id} game={game} />
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Loading more indicator */}
      {isLoadingMore && (
        <div className="mt-6 sm:mt-8">
          <DateGroupSkeleton count={3} />
        </div>
      )}

      {/* Load More button */}
      {hasMore && !isLoadingMore && (
        <div className="mt-6 sm:mt-8 text-center">
          <button
            onClick={loadMore}
            className="px-6 py-3 bg-gray-800 text-white rounded-lg hover:bg-gray-700 active:bg-gray-600 transition-colors font-medium min-h-[48px]"
            aria-label="Load more games"
          >
            Load More Games
          </button>
        </div>
      )}

      {/* End of list message */}
      {!hasMore && games.length > 0 && (
        <div className="mt-6 sm:mt-8 text-center text-gray-500 text-sm">
          You&apos;ve reached the end of the list
        </div>
      )}

      {/* Error loading more (but we have some data) */}
      {error && games.length > 0 && (
        <div className="mt-6 sm:mt-8 text-center">
          <p className="text-red-400 text-sm mb-2">{error}</p>
          <button
            onClick={loadMore}
            className="px-4 py-2 bg-gray-800 text-white rounded hover:bg-gray-700 transition-colors text-sm"
          >
            Try Again
          </button>
        </div>
      )}
    </>
  );
}

// Exported component wrapped with error boundary
export function GamesList(props: GamesListProps) {
  return (
    <GamesListErrorBoundary>
      <GamesListContent {...props} />
    </GamesListErrorBoundary>
  );
}

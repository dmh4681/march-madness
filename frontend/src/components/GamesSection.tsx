'use client';

import { useState, useMemo } from 'react';
import { format, parseISO } from 'date-fns';
import type { TodayGame } from '@/lib/types';
import { GameCard } from './GameCard';
import { GamesTable } from './GamesTable';

/**
 * Group games by date and return an array of [dateString, games[]] pairs
 * sorted by date ascending
 */
function groupGamesByDate(games: TodayGame[]): [string, TodayGame[]][] {
  const grouped = new Map<string, TodayGame[]>();

  for (const game of games) {
    const dateKey = game.date || 'Unknown';
    if (!grouped.has(dateKey)) {
      grouped.set(dateKey, []);
    }
    grouped.get(dateKey)!.push(game);
  }

  // Sort by date
  return Array.from(grouped.entries()).sort((a, b) => a[0].localeCompare(b[0]));
}

/**
 * Parse a date string (YYYY-MM-DD) as a local date, not UTC.
 * This prevents the off-by-one-day issue when displaying dates.
 */
function parseLocalDate(dateStr: string): Date {
  return new Date(dateStr + 'T12:00:00');
}

/**
 * Format a date string to a readable header (e.g., "Wednesday, January 22")
 */
function formatDateHeader(dateStr: string): string {
  if (dateStr === 'Unknown') return 'Unknown Date';
  try {
    return format(parseLocalDate(dateStr), 'EEEE, MMMM d');
  } catch {
    return dateStr;
  }
}

interface GamesSectionProps {
  games: TodayGame[];
}

type ViewMode = 'table' | 'cards';

export function GamesSection({ games }: GamesSectionProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('table');

  // Group games by date
  const gamesByDate = useMemo(() => groupGamesByDate(games), [games]);
  const hasMultipleDates = gamesByDate.length > 1;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white">
          Today&apos;s Games
        </h2>
        <div className="flex items-center gap-3">
          {/* View Toggle */}
          <div className="flex items-center bg-gray-800 rounded-lg p-0.5">
            <button
              onClick={() => setViewMode('table')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'table'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Table
            </button>
            <button
              onClick={() => setViewMode('cards')}
              className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                viewMode === 'cards'
                  ? 'bg-gray-700 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Cards
            </button>
          </div>

          {/* AI Legend */}
          <div className="hidden sm:flex items-center gap-3 text-xs text-gray-400">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500" />
              Claude
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-orange-500" />
              Grok
            </span>
          </div>
          {/* Confidence Legend */}
          <div className="hidden sm:flex items-center gap-2">
            <span className="text-xs px-2 py-0.5 bg-green-500/20 text-green-400 rounded">
              HIGH
            </span>
            <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">
              MED
            </span>
            <span className="text-xs px-2 py-0.5 bg-orange-500/20 text-orange-400 rounded">
              LOW
            </span>
          </div>
        </div>
      </div>

      {games.length === 0 ? (
        <div className="text-center py-12 text-gray-400">
          <p className="text-lg mb-2">No games scheduled for today</p>
          <p className="text-sm">
            Check back tomorrow or view upcoming games
          </p>
        </div>
      ) : hasMultipleDates ? (
        // Show games grouped by date with headers
        <div className="space-y-6">
          {gamesByDate.map(([dateStr, dateGames]) => (
            <div key={dateStr}>
              <h3 className="text-sm font-semibold text-blue-400 mb-3 border-b border-gray-700 pb-2">
                {formatDateHeader(dateStr)}
                <span className="text-gray-500 font-normal ml-2">
                  ({dateGames.length} {dateGames.length === 1 ? 'game' : 'games'})
                </span>
              </h3>
              {viewMode === 'table' ? (
                <GamesTable games={dateGames} />
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dateGames.map((game) => (
                    <GameCard key={game.id} game={game} />
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : viewMode === 'table' ? (
        <GamesTable games={games} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {games.map((game) => (
            <GameCard key={game.id} game={game} />
          ))}
        </div>
      )}
    </div>
  );
}

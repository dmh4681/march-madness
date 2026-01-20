'use client';

import { useState } from 'react';
import type { TodayGame } from '@/lib/types';
import { GameCard } from './GameCard';
import { GamesTable } from './GamesTable';

interface GamesSectionProps {
  games: TodayGame[];
}

type ViewMode = 'table' | 'cards';

export function GamesSection({ games }: GamesSectionProps) {
  const [viewMode, setViewMode] = useState<ViewMode>('table');

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

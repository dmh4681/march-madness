'use client';

import Link from 'next/link';
import type { TodayGame } from '@/lib/types';
import { formatSpread, formatMoneyline } from '@/lib/api';

interface GamesTableProps {
  games: TodayGame[];
  showAiPick?: boolean;
}

export function GamesTable({ games, showAiPick = false }: GamesTableProps) {
  if (games.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No games scheduled
      </div>
    );
  }

  // Check if any game has moneyline data
  const hasAnyMoneylines = games.some(g => g.home_ml !== null || g.away_ml !== null);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400 text-left">
            <th className="py-3 px-2 font-medium">Matchup</th>
            <th className="py-3 px-2 font-medium text-center">Spread</th>
            <th className="py-3 px-2 font-medium text-center">O/U</th>
            {hasAnyMoneylines && <th className="py-3 px-2 font-medium text-center">ML</th>}
            <th className="py-3 px-2 font-medium text-center">Pick</th>
            <th className="py-3 px-2 font-medium text-center">AI</th>
            <th className="py-3 px-2 font-medium text-center">Conf</th>
            <th className="py-3 px-2 font-medium text-center">Edge</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => (
            <GameRow key={game.id} game={game} showMoneyline={hasAnyMoneylines} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GameRow({ game, showMoneyline = true }: { game: TodayGame; showMoneyline?: boolean }) {
  const getConfidenceStyle = (tier: string | null) => {
    switch (tier) {
      case 'high':
        return 'bg-green-500/20 text-green-400';
      case 'medium':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'low':
        return 'bg-orange-500/20 text-orange-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  const getPickDisplay = () => {
    if (!game.recommended_bet || game.recommended_bet === 'pass') {
      return <span className="text-gray-500">-</span>;
    }

    const isHome = game.recommended_bet.includes('home');
    const team = isHome ? game.home_team : game.away_team;
    // Get short team name (first word or abbreviation)
    const shortName = team.split(' ')[0];
    const spread = isHome ? game.home_spread : (game.home_spread ? -game.home_spread : null);

    return (
      <span className="text-white font-medium">
        {shortName} {formatSpread(spread)}
      </span>
    );
  };

  return (
    <tr className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
      {/* Matchup */}
      <td className="py-3 px-2">
        <Link href={`/games/${game.id}`} className="block hover:text-blue-400">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-1">
              {game.away_rank && (
                <span className="text-yellow-500 text-xs font-bold">#{game.away_rank}</span>
              )}
              <span className="text-gray-300">{game.away_team}</span>
            </div>
            <div className="flex items-center gap-1">
              {game.home_rank && (
                <span className="text-yellow-500 text-xs font-bold">#{game.home_rank}</span>
              )}
              <span className="text-white">{game.home_team}</span>
              <span className="text-gray-600 text-xs">(H)</span>
            </div>
          </div>
        </Link>
      </td>

      {/* Spread */}
      <td className="py-3 px-2 text-center">
        <div className="flex flex-col text-xs">
          <span className="text-gray-400">{formatSpread(game.home_spread ? -game.home_spread : null)}</span>
          <span className="text-white">{formatSpread(game.home_spread)}</span>
        </div>
      </td>

      {/* O/U */}
      <td className="py-3 px-2 text-center text-gray-300">
        {game.over_under || '-'}
      </td>

      {/* Moneyline - only show if any game has ML data */}
      {showMoneyline && (
        <td className="py-3 px-2 text-center">
          <div className="flex flex-col text-xs">
            <span className={game.away_ml && game.away_ml > 0 ? 'text-green-400' : 'text-gray-400'}>
              {formatMoneyline(game.away_ml)}
            </span>
            <span className={game.home_ml && game.home_ml > 0 ? 'text-green-400' : 'text-gray-400'}>
              {formatMoneyline(game.home_ml)}
            </span>
          </div>
        </td>
      )}

      {/* Pick */}
      <td className="py-3 px-2 text-center">
        {getPickDisplay()}
      </td>

      {/* AI Indicators */}
      <td className="py-3 px-2 text-center">
        <div className="flex items-center justify-center gap-1">
          {game.has_claude_analysis && (
            <span
              className="w-2 h-2 rounded-full bg-blue-500"
              title="Claude analysis available"
            />
          )}
          {game.has_grok_analysis && (
            <span
              className="w-2 h-2 rounded-full bg-orange-500"
              title="Grok analysis available"
            />
          )}
          {!game.has_claude_analysis && !game.has_grok_analysis && (
            <span className="text-gray-600 text-xs">-</span>
          )}
        </div>
      </td>

      {/* Confidence */}
      <td className="py-3 px-2 text-center">
        {game.confidence_tier && game.confidence_tier !== 'pass' ? (
          <span className={`px-2 py-0.5 rounded text-xs font-medium ${getConfidenceStyle(game.confidence_tier)}`}>
            {game.confidence_tier.toUpperCase()}
          </span>
        ) : (
          <span className="text-gray-500">-</span>
        )}
      </td>

      {/* Edge */}
      <td className="py-3 px-2 text-center">
        {game.edge_pct && game.edge_pct > 0 ? (
          <span className="text-green-400 font-medium">
            +{game.edge_pct.toFixed(1)}%
          </span>
        ) : (
          <span className="text-gray-500">-</span>
        )}
      </td>
    </tr>
  );
}

// Compact single-line version for even denser display
export function GamesTableCompact({ games }: GamesTableProps) {
  if (games.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No games scheduled
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-700 text-gray-400">
            <th className="py-2 px-1 font-medium text-left">Away</th>
            <th className="py-2 px-1 font-medium text-left">Home</th>
            <th className="py-2 px-1 font-medium text-center">Spread</th>
            <th className="py-2 px-1 font-medium text-center">Pick</th>
            <th className="py-2 px-1 font-medium text-center">AI</th>
            <th className="py-2 px-1 font-medium text-center">Edge</th>
          </tr>
        </thead>
        <tbody>
          {games.map((game) => {
            const isHomePick = game.recommended_bet?.includes('home');
            const pickTeam = isHomePick ? game.home_team.split(' ')[0] : game.away_team.split(' ')[0];
            const hasPick = game.recommended_bet && game.recommended_bet !== 'pass';

            return (
              <tr key={game.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                <td className="py-2 px-1">
                  <Link href={`/games/${game.id}`} className="hover:text-blue-400">
                    {game.away_rank && <span className="text-yellow-500">#{game.away_rank} </span>}
                    <span className="text-gray-300">{game.away_team.split(' ')[0]}</span>
                  </Link>
                </td>
                <td className="py-2 px-1">
                  <Link href={`/games/${game.id}`} className="hover:text-blue-400">
                    {game.home_rank && <span className="text-yellow-500">#{game.home_rank} </span>}
                    <span className="text-white">{game.home_team.split(' ')[0]}</span>
                  </Link>
                </td>
                <td className="py-2 px-1 text-center text-gray-400">
                  {formatSpread(game.home_spread)}
                </td>
                <td className="py-2 px-1 text-center">
                  {hasPick ? (
                    <span className={`font-medium ${
                      game.confidence_tier === 'high' ? 'text-green-400' :
                      game.confidence_tier === 'medium' ? 'text-yellow-400' : 'text-gray-400'
                    }`}>
                      {pickTeam}
                    </span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
                <td className="py-2 px-1 text-center">
                  <div className="flex items-center justify-center gap-0.5">
                    {game.has_claude_analysis && (
                      <span className="w-1.5 h-1.5 rounded-full bg-blue-500" title="Claude" />
                    )}
                    {game.has_grok_analysis && (
                      <span className="w-1.5 h-1.5 rounded-full bg-orange-500" title="Grok" />
                    )}
                    {!game.has_claude_analysis && !game.has_grok_analysis && (
                      <span className="text-gray-600">-</span>
                    )}
                  </div>
                </td>
                <td className="py-2 px-1 text-center">
                  {game.edge_pct && game.edge_pct > 0 ? (
                    <span className="text-green-400">+{game.edge_pct.toFixed(0)}%</span>
                  ) : (
                    <span className="text-gray-600">-</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

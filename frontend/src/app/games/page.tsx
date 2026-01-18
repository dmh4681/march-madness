import { format, addDays } from 'date-fns';
import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { GameCard } from '@/components/GameCard';
import type { TodayGame } from '@/lib/types';

// Demo data for games listing
const DEMO_GAMES: TodayGame[] = [
  {
    id: 'demo-1',
    date: new Date().toISOString(),
    tip_time: new Date(Date.now() + 3600000).toISOString(),
    home_team: 'Duke Blue Devils',
    home_conference: 'ACC',
    away_team: 'North Carolina Tar Heels',
    away_conference: 'ACC',
    is_conference_game: true,
    home_spread: -3.5,
    home_ml: -160,
    away_ml: 140,
    over_under: 145.5,
    home_rank: 9,
    away_rank: 7,
    predicted_home_cover_prob: 0.58,
    confidence_tier: 'medium',
    recommended_bet: 'home_spread',
    edge_pct: 4.2,
  },
  {
    id: 'demo-2',
    date: new Date().toISOString(),
    tip_time: new Date(Date.now() + 7200000).toISOString(),
    home_team: 'Houston Cougars',
    home_conference: 'Big 12',
    away_team: 'Kansas Jayhawks',
    away_conference: 'Big 12',
    is_conference_game: true,
    home_spread: -5.5,
    home_ml: -220,
    away_ml: 180,
    over_under: 138.5,
    home_rank: 3,
    away_rank: 12,
    predicted_home_cover_prob: 0.62,
    confidence_tier: 'high',
    recommended_bet: 'home_spread',
    edge_pct: 7.8,
  },
  {
    id: 'demo-3',
    date: addDays(new Date(), 1).toISOString(),
    tip_time: addDays(new Date(), 1).toISOString(),
    home_team: 'Kentucky Wildcats',
    home_conference: 'SEC',
    away_team: 'Tennessee Volunteers',
    away_conference: 'SEC',
    is_conference_game: true,
    home_spread: 2.5,
    home_ml: 115,
    away_ml: -135,
    over_under: 151.0,
    home_rank: null,
    away_rank: 5,
    predicted_home_cover_prob: 0.55,
    confidence_tier: 'high',
    recommended_bet: 'home_spread',
    edge_pct: 6.1,
  },
  {
    id: 'demo-4',
    date: addDays(new Date(), 1).toISOString(),
    tip_time: addDays(new Date(), 1).toISOString(),
    home_team: 'UCLA Bruins',
    home_conference: 'Big Ten',
    away_team: 'Arizona Wildcats',
    away_conference: 'Big 12',
    is_conference_game: false,
    home_spread: 1.5,
    home_ml: -105,
    away_ml: -115,
    over_under: 142.0,
    home_rank: 15,
    away_rank: 8,
    predicted_home_cover_prob: 0.48,
    confidence_tier: 'low',
    recommended_bet: 'pass',
    edge_pct: null,
  },
  {
    id: 'demo-5',
    date: addDays(new Date(), 2).toISOString(),
    tip_time: addDays(new Date(), 2).toISOString(),
    home_team: 'Gonzaga Bulldogs',
    home_conference: 'WCC',
    away_team: 'Saint Mary\'s Gaels',
    away_conference: 'WCC',
    is_conference_game: true,
    home_spread: -8.5,
    home_ml: -350,
    away_ml: 280,
    over_under: 148.5,
    home_rank: 6,
    away_rank: 22,
    predicted_home_cover_prob: 0.52,
    confidence_tier: 'low',
    recommended_bet: 'pass',
    edge_pct: null,
  },
  {
    id: 'demo-6',
    date: addDays(new Date(), 2).toISOString(),
    tip_time: addDays(new Date(), 2).toISOString(),
    home_team: 'Purdue Boilermakers',
    home_conference: 'Big Ten',
    away_team: 'Michigan State Spartans',
    away_conference: 'Big Ten',
    is_conference_game: true,
    home_spread: -6.0,
    home_ml: -240,
    away_ml: 195,
    over_under: 139.5,
    home_rank: 2,
    away_rank: 18,
    predicted_home_cover_prob: 0.61,
    confidence_tier: 'high',
    recommended_bet: 'home_spread',
    edge_pct: 5.9,
  },
];

async function getUpcomingGames(): Promise<TodayGame[]> {
  if (!isSupabaseConfigured()) {
    return DEMO_GAMES;
  }

  // Get games from next 7 days
  const today = new Date().toISOString().split('T')[0];
  const nextWeek = addDays(new Date(), 7).toISOString().split('T')[0];

  const { data, error } = await supabase
    .from('games')
    .select(`
      id,
      date,
      season,
      is_conference_game,
      home_team:home_team_id(name, conference),
      away_team:away_team_id(name, conference)
    `)
    .gte('date', today)
    .lte('date', nextWeek)
    .order('date', { ascending: true }) as { data: unknown[] | null; error: unknown };

  if (error || !data) {
    return DEMO_GAMES;
  }

  // Transform to TodayGame format
  return data.map((game: Record<string, unknown>) => {
    const homeTeam = game.home_team as { name: string; conference: string } | null;
    const awayTeam = game.away_team as { name: string; conference: string } | null;

    return {
      id: game.id as string,
      date: game.date as string,
      tip_time: game.date as string,
      home_team: homeTeam?.name || 'TBD',
      home_conference: homeTeam?.conference || '',
      away_team: awayTeam?.name || 'TBD',
      away_conference: awayTeam?.conference || '',
      is_conference_game: game.is_conference_game as boolean,
      home_spread: null,
      home_ml: null,
      away_ml: null,
      over_under: null,
      home_rank: null,
      away_rank: null,
      predicted_home_cover_prob: null,
      confidence_tier: null,
      recommended_bet: null,
      edge_pct: null,
    };
  });
}

// Group games by date
function groupGamesByDate(games: TodayGame[]): Record<string, TodayGame[]> {
  return games.reduce((acc, game) => {
    const dateKey = game.date.split('T')[0];
    if (!acc[dateKey]) {
      acc[dateKey] = [];
    }
    acc[dateKey].push(game);
    return acc;
  }, {} as Record<string, TodayGame[]>);
}

export default async function GamesPage() {
  const games = await getUpcomingGames();
  const gamesByDate = groupGamesByDate(games);
  const isDemo = !isSupabaseConfigured();

  const highConfidenceCount = games.filter(g => g.confidence_tier === 'high').length;

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <Link href="/" className="text-2xl font-bold text-white hover:text-gray-300 transition-colors">
                Conference Contrarian
              </Link>
              <p className="text-sm text-gray-400">
                AI-Powered College Basketball Betting Analysis
              </p>
            </div>
            <nav className="flex items-center gap-6">
              <Link
                href="/games"
                className="text-white font-medium"
              >
                All Games
              </Link>
              <Link
                href="/march-madness"
                className="text-gray-400 hover:text-white transition-colors"
              >
                March Madness
              </Link>
              <Link
                href="/performance"
                className="text-gray-400 hover:text-white transition-colors"
              >
                Performance
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Demo Banner */}
      {isDemo && (
        <div className="bg-yellow-500/10 border-b border-yellow-500/30">
          <div className="max-w-7xl mx-auto px-4 py-2">
            <p className="text-sm text-yellow-400 text-center">
              Demo Mode - Showing sample data
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Upcoming Games</h1>
          <p className="text-gray-400">
            {games.length} games over the next 7 days
            {highConfidenceCount > 0 && (
              <span className="ml-2 text-green-400">
                ({highConfidenceCount} high confidence picks)
              </span>
            )}
          </p>
        </div>

        {/* Filters */}
        <div className="flex gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded cursor-pointer hover:bg-green-500/30">
              High Confidence
            </span>
            <span className="text-xs px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded cursor-pointer hover:bg-yellow-500/30">
              Medium
            </span>
            <span className="text-xs px-2 py-1 bg-gray-700 text-gray-400 rounded cursor-pointer hover:bg-gray-600">
              All Games
            </span>
          </div>
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs px-2 py-1 bg-blue-500/20 text-blue-400 rounded cursor-pointer hover:bg-blue-500/30">
              Conference Only
            </span>
            <span className="text-xs px-2 py-1 bg-purple-500/20 text-purple-400 rounded cursor-pointer hover:bg-purple-500/30">
              Ranked Matchups
            </span>
          </div>
        </div>

        {/* Games by Date */}
        <div className="space-y-8">
          {Object.entries(gamesByDate).map(([dateStr, dateGames]) => (
            <div key={dateStr}>
              <h2 className="text-lg font-semibold text-white mb-4 border-b border-gray-800 pb-2">
                {format(new Date(dateStr), 'EEEE, MMMM d, yyyy')}
                <span className="text-sm font-normal text-gray-400 ml-2">
                  ({dateGames.length} games)
                </span>
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {dateGames.map((game) => (
                  <GameCard key={game.id} game={game} />
                ))}
              </div>
            </div>
          ))}
        </div>

        {games.length === 0 && (
          <div className="text-center py-12 text-gray-400">
            <p className="text-lg mb-2">No upcoming games found</p>
            <p className="text-sm">Check back later for new matchups</p>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-12">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <p className="text-center text-sm text-gray-500">
            For entertainment purposes only. Please gamble responsibly.
          </p>
        </div>
      </footer>
    </div>
  );
}

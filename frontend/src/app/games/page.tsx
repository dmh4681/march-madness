import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { GamesList } from '@/components/GamesList';
import type { TodayGame } from '@/lib/types';

// Force dynamic rendering to always fetch fresh data
export const dynamic = 'force-dynamic';
export const revalidate = 0;

// Demo data for games listing - uses static dates to avoid hydration mismatches
const DEMO_GAMES: TodayGame[] = [
  {
    id: 'demo-1',
    date: '2025-01-22',
    tip_time: '2025-01-22T19:00:00Z',
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
    date: '2025-01-22',
    tip_time: '2025-01-22T21:00:00Z',
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
    date: '2025-01-23',
    tip_time: '2025-01-23T19:00:00Z',
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
    date: '2025-01-23',
    tip_time: '2025-01-23T21:00:00Z',
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
    date: '2025-01-24',
    tip_time: '2025-01-24T19:00:00Z',
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
    date: '2025-01-24',
    tip_time: '2025-01-24T21:00:00Z',
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

// Server-side fetch for initial page (first 20 games)
async function getInitialGames(): Promise<TodayGame[]> {
  if (!isSupabaseConfigured()) {
    return DEMO_GAMES;
  }

  // Fetch first page from the upcoming_games view
  const { data, error } = await supabase
    .from('upcoming_games')
    .select('*')
    .order('date', { ascending: true })
    .limit(20);

  if (error || !data || data.length === 0) {
    console.error('Error fetching upcoming games:', error);
    return DEMO_GAMES;
  }

  return data as TodayGame[];
}

export default async function GamesPage() {
  const initialGames = await getInitialGames();
  const isDemo = !isSupabaseConfigured();

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header - responsive with mobile menu */}
      <header className="border-b border-gray-800 bg-gray-900/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div className="min-w-0 flex-1 sm:flex-initial">
              <Link href="/" className="text-xl sm:text-2xl font-bold text-white hover:text-gray-300 transition-colors">
                Conference Contrarian
              </Link>
              <p className="text-xs sm:text-sm text-gray-400 truncate">
                AI-Powered CBB Betting
              </p>
            </div>
            {/* Desktop navigation */}
            <nav className="hidden sm:flex items-center gap-6" aria-label="Main navigation">
              <Link
                href="/games"
                className="text-white font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded"
                aria-current="page"
              >
                All Games
              </Link>
              <Link
                href="/march-madness"
                className="text-gray-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded"
              >
                March Madness
              </Link>
              <Link
                href="/performance"
                className="text-gray-400 hover:text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-gray-900 rounded"
              >
                Performance
              </Link>
            </nav>
            {/* Mobile navigation */}
            <nav className="sm:hidden flex items-center gap-1" aria-label="Mobile navigation">
              <Link
                href="/games"
                className="px-3 py-2 min-h-[44px] flex items-center text-sm text-white font-medium"
                aria-label="All Games"
                aria-current="page"
              >
                Games
              </Link>
              <Link
                href="/march-madness"
                className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-400"
                aria-label="March Madness"
              >
                MM
              </Link>
              <Link
                href="/performance"
                className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-400"
                aria-label="Performance Stats"
              >
                Stats
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
      <main id="main-content" className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8" tabIndex={-1}>
        {/* Filters - horizontally scrollable on mobile */}
        <div className="mb-4 sm:mb-6 -mx-3 px-3 sm:mx-0 sm:px-0">
          <div className="flex gap-2 sm:gap-4 overflow-x-auto pb-2 sm:pb-0 scrollbar-hide">
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-xs px-3 py-2 min-h-[40px] sm:min-h-0 sm:py-1 flex items-center bg-green-500/20 text-green-400 rounded cursor-pointer hover:bg-green-500/30 active:bg-green-500/40 transition-colors">
                High Confidence
              </span>
              <span className="text-xs px-3 py-2 min-h-[40px] sm:min-h-0 sm:py-1 flex items-center bg-yellow-500/20 text-yellow-400 rounded cursor-pointer hover:bg-yellow-500/30 active:bg-yellow-500/40 transition-colors">
                Medium
              </span>
              <span className="text-xs px-3 py-2 min-h-[40px] sm:min-h-0 sm:py-1 flex items-center bg-gray-700 text-gray-400 rounded cursor-pointer hover:bg-gray-600 active:bg-gray-500 transition-colors">
                All Games
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0 sm:ml-auto">
              <span className="text-xs px-3 py-2 min-h-[40px] sm:min-h-0 sm:py-1 flex items-center bg-blue-500/20 text-blue-400 rounded cursor-pointer hover:bg-blue-500/30 active:bg-blue-500/40 transition-colors whitespace-nowrap">
                Conference Only
              </span>
              <span className="text-xs px-3 py-2 min-h-[40px] sm:min-h-0 sm:py-1 flex items-center bg-purple-500/20 text-purple-400 rounded cursor-pointer hover:bg-purple-500/30 active:bg-purple-500/40 transition-colors whitespace-nowrap">
                Ranked Matchups
              </span>
            </div>
          </div>
        </div>

        {/* Games List with Load More */}
        <GamesList initialGames={initialGames} days={7} />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-8 sm:mt-12">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:py-6">
          <p className="text-center text-xs sm:text-sm text-gray-500">
            For entertainment purposes only. Please gamble responsibly.
          </p>
        </div>
      </footer>
    </div>
  );
}

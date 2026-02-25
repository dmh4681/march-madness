import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { BracketMatchup, RegionSeedEntry, Tournament, TournamentStatus } from '@/lib/types';
import { BracketView } from './BracketView';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

// ============================================
// Data Fetching
// ============================================

async function getBracketData(): Promise<{
  tournament: Tournament | null;
  matchups: BracketMatchup[];
  regionSeeds: RegionSeedEntry[];
}> {
  if (!isSupabaseConfigured()) {
    return { tournament: null, matchups: [], regionSeeds: [] };
  }

  const currentSeason = new Date().getFullYear();

  const [tournamentResult, matchupsResult, seedsResult] = await Promise.all([
    supabase
      .from('tournaments')
      .select('*')
      .eq('season', currentSeason)
      .single(),
    supabase
      .from('tournament_bracket')
      .select('*')
      .eq('season', currentSeason)
      .order('date', { ascending: true }),
    supabase
      .from('tournament_region_summary')
      .select('*')
      .eq('season', currentSeason)
      .order('region', { ascending: true }),
  ]);

  return {
    tournament: (tournamentResult.data as Tournament | null) ?? null,
    matchups: (matchupsResult.data as BracketMatchup[] | null) ?? [],
    regionSeeds: (seedsResult.data as RegionSeedEntry[] | null) ?? [],
  };
}

// ============================================
// Status Badge
// ============================================

const STATUS_CONFIG: Record<TournamentStatus, { label: string; color: string; pulse?: boolean }> = {
  upcoming: { label: 'Bracket Pending', color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  bracket_set: { label: 'Bracket Set', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
  in_progress: { label: 'In Progress', color: 'bg-green-500/20 text-green-400 border-green-500/30', pulse: true },
  completed: { label: 'Completed', color: 'bg-gray-500/20 text-gray-400 border-gray-500/30' },
};

// ============================================
// Page (Server Component)
// ============================================

export default async function MarchMadnessPage() {
  const { tournament, matchups, regionSeeds } = await getBracketData();
  const isDemo = !isSupabaseConfigured();

  // Compute stats server-side to avoid hydration issues
  const totalTeams = regionSeeds.length;
  const pickedCount = matchups.filter(m => m.picked_team_id !== null).length;
  const gradedCount = matchups.filter(m => m.is_correct !== null).length;
  const correctCount = matchups.filter(m => m.is_correct === true).length;
  const correctPct = gradedCount > 0 ? Math.round((correctCount / gradedCount) * 100) : null;

  const statusConfig = tournament?.status ? STATUS_CONFIG[tournament.status] : null;

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
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
            <nav className="hidden sm:flex items-center gap-6">
              <Link href="/games" className="text-gray-400 hover:text-white transition-colors">
                All Games
              </Link>
              <Link href="/march-madness" className="text-white font-medium">
                March Madness
              </Link>
              <Link href="/performance" className="text-gray-400 hover:text-white transition-colors">
                Performance
              </Link>
            </nav>
            {/* Mobile navigation */}
            <nav className="sm:hidden flex items-center gap-1" aria-label="Mobile navigation">
              <Link
                href="/games"
                className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-400"
                aria-label="All Games"
              >
                Games
              </Link>
              <Link
                href="/march-madness"
                className="px-3 py-2 min-h-[44px] flex items-center text-sm text-white font-medium"
                aria-label="March Madness"
                aria-current="page"
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

      {/* Hero Section */}
      <div className="bg-gradient-to-b from-orange-900/20 to-black border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-6 sm:py-12">
          <div className="flex items-center gap-3 mb-1 sm:mb-2">
            <h1 className="text-2xl sm:text-4xl font-bold text-white">
              March Madness 2026
            </h1>
            {statusConfig && (
              <span className={`text-xs sm:text-sm font-semibold px-2.5 py-1 rounded-md border ${statusConfig.color} flex items-center gap-1.5`}>
                {statusConfig.pulse && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
                )}
                {statusConfig.label}
              </span>
            )}
          </div>
          <p className="text-base sm:text-xl text-gray-400 mb-4 sm:mb-6">
            NCAA Tournament Analysis
          </p>
          {/* Stats badges */}
          <div className="flex gap-2 sm:gap-4 overflow-x-auto pb-2 sm:pb-0 scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
            <div className="bg-orange-500/20 border border-orange-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0">
              <span className="text-orange-400 font-semibold text-sm sm:text-base">
                {totalTeams > 0 ? `${totalTeams} Teams` : '68 Teams'}
              </span>
            </div>
            <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0">
              <span className="text-blue-400 font-semibold text-sm sm:text-base">
                {matchups.length > 0 ? `${matchups.length} Games` : '67 Games'}
              </span>
            </div>
            {pickedCount > 0 ? (
              <div className="bg-green-500/20 border border-green-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0 whitespace-nowrap">
                <span className="text-green-400 font-semibold text-sm sm:text-base">
                  {pickedCount} Picks{correctPct !== null ? ` (${correctPct}%)` : ''}
                </span>
              </div>
            ) : (
              <div className="bg-green-500/20 border border-green-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0 whitespace-nowrap">
                <span className="text-green-400 font-semibold text-sm sm:text-base">AI Analysis</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        <BracketView
          tournament={tournament}
          matchups={matchups}
          regionSeeds={regionSeeds}
          isDemo={isDemo}
          pickedCount={pickedCount}
          correctPct={correctPct}
        />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-800 mt-8 sm:mt-12 safe-area-bottom">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:py-6">
          <p className="text-center text-xs sm:text-sm text-gray-500">
            For entertainment purposes only. Please gamble responsibly.
          </p>
        </div>
      </footer>
    </div>
  );
}

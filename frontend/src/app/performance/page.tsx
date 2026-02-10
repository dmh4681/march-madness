import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import { PerformanceStats } from '@/components/PerformanceStats';

export const dynamic = 'force-dynamic';
export const revalidate = 0;

async function getPerformanceData() {
  if (!isSupabaseConfigured()) {
    return { betResults: [], seasonPerformance: null };
  }

  // Fetch bet results with joined prediction confidence tier and game teams
  const { data: betResults } = await supabase
    .from('bet_results')
    .select('*, predictions:prediction_id(confidence_tier), games:game_id(home_team_id, away_team_id, date)')
    .order('created_at', { ascending: false })
    .limit(200);

  // Fetch season performance view
  const { data: seasonPerf } = await supabase
    .from('season_performance')
    .select('*')
    .order('season', { ascending: false })
    .limit(1);

  // Map bet results to include confidence tier from joined prediction
  const mapped = (betResults ?? []).map((b: Record<string, unknown>) => {
    const pred = b.predictions as Record<string, unknown> | null;
    const game = b.games as Record<string, unknown> | null;
    return {
      ...b,
      predictions: undefined,
      games: undefined,
      confidence_tier: pred?.confidence_tier ?? null,
      home_team: game?.home_team_id ?? null,
      away_team: game?.away_team_id ?? null,
      date: game?.date ?? null,
    };
  });

  return {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    betResults: mapped as any[],
    seasonPerformance: seasonPerf?.[0] ?? null,
  };
}

export default async function PerformancePage() {
  const { betResults, seasonPerformance } = await getPerformanceData();
  const isDemo = !isSupabaseConfigured();

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
              <Link href="/march-madness" className="text-gray-400 hover:text-white transition-colors">
                March Madness
              </Link>
              <Link href="/performance" className="text-white font-medium" aria-current="page">
                Performance
              </Link>
            </nav>
            {/* Mobile navigation */}
            <nav className="sm:hidden flex items-center gap-1">
              <Link href="/games" className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-400">
                Games
              </Link>
              <Link href="/march-madness" className="px-3 py-2 min-h-[44px] flex items-center text-sm text-gray-400">
                MM
              </Link>
              <Link href="/performance" className="px-3 py-2 min-h-[44px] flex items-center text-sm text-white font-medium" aria-current="page">
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
              Demo Mode - Connect Supabase to see real performance data
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        <div className="mb-4 sm:mb-8">
          <h1 className="text-2xl sm:text-3xl font-bold text-white mb-1 sm:mb-2">Performance Tracking</h1>
          <p className="text-sm sm:text-base text-gray-400">
            Season results, confidence tier breakdown, and recent picks
          </p>
        </div>

        <PerformanceStats betResults={betResults} seasonPerformance={seasonPerformance} />
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

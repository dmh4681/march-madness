import { format } from 'date-fns';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';
import type { TodayGame, DashboardStats } from '@/lib/types';
import { GameCard } from '@/components/GameCard';
import { PicksList, StatsCard } from '@/components/PicksList';

// Demo data for when Supabase isn't configured
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
    date: new Date().toISOString(),
    tip_time: new Date(Date.now() + 10800000).toISOString(),
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
    date: new Date().toISOString(),
    tip_time: new Date(Date.now() + 14400000).toISOString(),
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
];

const DEMO_STATS: DashboardStats = {
  season_roi: 8.4,
  win_rate: 56.2,
  total_bets: 89,
  current_streak: 3,
  streak_type: 'W',
};

async function getTodayGames(): Promise<TodayGame[]> {
  if (!isSupabaseConfigured()) {
    return DEMO_GAMES;
  }

  const { data, error } = await supabase
    .from('today_games')
    .select('*')
    .order('tip_time', { ascending: true });

  if (error) {
    console.error('Error fetching games:', error);
    return DEMO_GAMES;
  }

  return data || [];
}

async function getStats(): Promise<DashboardStats> {
  if (!isSupabaseConfigured()) {
    return DEMO_STATS;
  }

  const currentSeason = new Date().getFullYear();

  const { data, error } = await supabase
    .from('season_performance')
    .select('*')
    .eq('season', currentSeason)
    .single() as {
      data: { roi_pct: number; win_pct: number; total_bets: number } | null;
      error: unknown;
    };

  if (error || !data) {
    return DEMO_STATS;
  }

  // Calculate streak from recent bet results
  const { data: recentBetsData } = await supabase
    .from('bet_results')
    .select('result')
    .order('created_at', { ascending: false })
    .limit(10) as { data: Array<{ result: string }> | null };

  let streak = { count: 0, type: 'W' as 'W' | 'L' };
  const recentBets = recentBetsData || [];
  if (recentBets.length > 0) {
    const firstResult = recentBets[0].result;
    if (firstResult === 'win' || firstResult === 'loss') {
      streak.type = firstResult === 'win' ? 'W' : 'L';
      for (const bet of recentBets) {
        if (
          (streak.type === 'W' && bet.result === 'win') ||
          (streak.type === 'L' && bet.result === 'loss')
        ) {
          streak.count++;
        } else {
          break;
        }
      }
    }
  }

  return {
    season_roi: data.roi_pct || 0,
    win_rate: data.win_pct || 0,
    total_bets: data.total_bets || 0,
    current_streak: streak.count,
    streak_type: streak.type,
  };
}

export default async function Dashboard() {
  const [games, stats] = await Promise.all([getTodayGames(), getStats()]);

  const today = format(new Date(), 'EEEE, MMMM d, yyyy');
  const isDemo = !isSupabaseConfigured();

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-white">
                Conference Contrarian
              </h1>
              <p className="text-sm text-gray-400">
                AI-Powered College Basketball Betting Analysis
              </p>
            </div>
            <nav className="flex items-center gap-6">
              <a
                href="/games"
                className="text-gray-400 hover:text-white transition-colors"
              >
                All Games
              </a>
              <a
                href="/march-madness"
                className="text-gray-400 hover:text-white transition-colors"
              >
                March Madness
              </a>
              <a
                href="/performance"
                className="text-gray-400 hover:text-white transition-colors"
              >
                Performance
              </a>
            </nav>
          </div>
        </div>
      </header>

      {/* Demo Banner */}
      {isDemo && (
        <div className="bg-yellow-500/10 border-b border-yellow-500/30">
          <div className="max-w-7xl mx-auto px-4 py-2">
            <p className="text-sm text-yellow-400 text-center">
              Demo Mode - Configure Supabase environment variables to connect to
              your database
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Date Header */}
        <div className="mb-6">
          <h2 className="text-xl font-semibold text-white">{today}</h2>
          <p className="text-gray-400">
            {games.length} {games.length === 1 ? 'game' : 'games'} on the slate
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Stats & Picks */}
          <div className="space-y-6">
            <StatsCard
              seasonRoi={stats.season_roi}
              winRate={stats.win_rate}
              totalBets={stats.total_bets}
              streak={
                stats.current_streak > 0
                  ? { count: stats.current_streak, type: stats.streak_type! }
                  : null
              }
            />
            <PicksList games={games} />
          </div>

          {/* Right Column - All Games */}
          <div className="lg:col-span-2">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">
                  Today&apos;s Games
                </h2>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-1 bg-green-500/20 text-green-400 rounded">
                    🔥 HIGH
                  </span>
                  <span className="text-xs px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded">
                    ⚡ MED
                  </span>
                  <span className="text-xs px-2 py-1 bg-orange-500/20 text-orange-400 rounded">
                    📊 LOW
                  </span>
                </div>
              </div>

              {games.length === 0 ? (
                <div className="text-center py-12 text-gray-400">
                  <p className="text-lg mb-2">No games scheduled for today</p>
                  <p className="text-sm">
                    Check back tomorrow or view upcoming games
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {games.map((game) => (
                    <GameCard key={game.id} game={game} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
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

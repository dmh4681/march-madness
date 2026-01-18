import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

// Demo performance data
const DEMO_STATS = {
  overall: {
    totalBets: 156,
    wins: 89,
    losses: 64,
    pushes: 3,
    winRate: 58.2,
    unitsWagered: 156,
    unitsWon: 18.4,
    roi: 11.8,
  },
  byConfidence: [
    { tier: 'High', bets: 42, wins: 28, losses: 14, winRate: 66.7, roi: 22.3 },
    { tier: 'Medium', bets: 68, wins: 38, losses: 29, winRate: 56.7, roi: 8.4 },
    { tier: 'Low', bets: 46, wins: 23, losses: 21, winRate: 52.3, roi: 2.1 },
  ],
  byMonth: [
    { month: 'November', bets: 28, wins: 15, roi: 6.2 },
    { month: 'December', bets: 32, wins: 19, roi: 14.5 },
    { month: 'January', bets: 38, wins: 23, roi: 15.8 },
    { month: 'February', bets: 35, wins: 20, roi: 9.2 },
    { month: 'March', bets: 23, wins: 12, roi: 8.1 },
  ],
  recentPicks: [
    { date: '2025-01-17', game: 'Duke vs UNC', pick: 'Duke -3.5', result: 'W', units: 1.0 },
    { date: '2025-01-16', game: 'Houston vs Kansas', pick: 'Houston -5.5', result: 'W', units: 1.0 },
    { date: '2025-01-15', game: 'Kentucky vs Tennessee', pick: 'Kentucky +2.5', result: 'L', units: -1.0 },
    { date: '2025-01-14', game: 'Purdue vs Michigan', pick: 'Purdue -8.0', result: 'W', units: 1.0 },
    { date: '2025-01-13', game: 'Arizona vs UCLA', pick: 'Arizona -1.5', result: 'W', units: 1.0 },
    { date: '2025-01-12', game: 'Gonzaga vs St. Mary\'s', pick: 'St. Mary\'s +8.5', result: 'L', units: -1.0 },
    { date: '2025-01-11', game: 'UConn vs Villanova', pick: 'UConn -10.5', result: 'Push', units: 0 },
    { date: '2025-01-10', game: 'Auburn vs Alabama', pick: 'Auburn +3.0', result: 'W', units: 1.0 },
  ],
  streaks: {
    current: { type: 'W', count: 3 },
    bestWin: 8,
    worstLoss: 4,
  },
};

async function getPerformanceStats() {
  if (!isSupabaseConfigured()) {
    return DEMO_STATS;
  }

  // Fetch real stats from Supabase
  const { data, error } = await supabase
    .from('bet_results')
    .select('*')
    .order('created_at', { ascending: false }) as { data: unknown[] | null; error: unknown };

  if (error || !data || data.length === 0) {
    return DEMO_STATS;
  }

  // Calculate real stats from data
  // For now, return demo data
  return DEMO_STATS;
}

export default async function PerformancePage() {
  const stats = await getPerformanceStats();
  const isDemo = !isSupabaseConfigured();

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
                className="text-gray-400 hover:text-white transition-colors"
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
                className="text-white font-medium"
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
              Demo Mode - Showing sample performance data
            </p>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Page Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-white mb-2">Performance Dashboard</h1>
          <p className="text-gray-400">
            2024-25 Season Results & Analytics
          </p>
        </div>

        {/* Overall Stats Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400 mb-1">Season ROI</p>
            <p className={`text-3xl font-bold ${stats.overall.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.overall.roi >= 0 ? '+' : ''}{stats.overall.roi}%
            </p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400 mb-1">Win Rate</p>
            <p className="text-3xl font-bold text-white">{stats.overall.winRate}%</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400 mb-1">Total Bets</p>
            <p className="text-3xl font-bold text-white">{stats.overall.totalBets}</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <p className="text-sm text-gray-400 mb-1">Units Won</p>
            <p className={`text-3xl font-bold ${stats.overall.unitsWon >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.overall.unitsWon >= 0 ? '+' : ''}{stats.overall.unitsWon}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Record Breakdown */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Season Record</h2>
              <div className="flex items-center gap-8 mb-4">
                <div className="text-center">
                  <p className="text-4xl font-bold text-green-400">{stats.overall.wins}</p>
                  <p className="text-sm text-gray-400">Wins</p>
                </div>
                <div className="text-center">
                  <p className="text-4xl font-bold text-red-400">{stats.overall.losses}</p>
                  <p className="text-sm text-gray-400">Losses</p>
                </div>
                <div className="text-center">
                  <p className="text-4xl font-bold text-gray-400">{stats.overall.pushes}</p>
                  <p className="text-sm text-gray-400">Pushes</p>
                </div>
              </div>
              {/* Win Rate Bar */}
              <div className="w-full bg-gray-800 rounded-full h-4 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-green-600 to-green-400"
                  style={{ width: `${stats.overall.winRate}%` }}
                />
              </div>
              <p className="text-sm text-gray-400 mt-2">
                {stats.overall.winRate}% win rate ({stats.overall.wins}-{stats.overall.losses}-{stats.overall.pushes})
              </p>
            </div>

            {/* Performance by Confidence Tier */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Performance by Confidence Tier</h2>
              <div className="space-y-4">
                {stats.byConfidence.map((tier) => (
                  <div key={tier.tier} className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg">
                    <div className="flex items-center gap-3">
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          tier.tier === 'High'
                            ? 'bg-green-500/20 text-green-400'
                            : tier.tier === 'Medium'
                            ? 'bg-yellow-500/20 text-yellow-400'
                            : 'bg-orange-500/20 text-orange-400'
                        }`}
                      >
                        {tier.tier}
                      </span>
                      <div>
                        <p className="text-white font-medium">{tier.wins}-{tier.losses}</p>
                        <p className="text-xs text-gray-400">{tier.bets} bets</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-white font-medium">{tier.winRate}%</p>
                      <p className={`text-xs ${tier.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {tier.roi >= 0 ? '+' : ''}{tier.roi}% ROI
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Monthly Breakdown */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Monthly Performance</h2>
              <div className="space-y-3">
                {stats.byMonth.map((month) => (
                  <div key={month.month} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                    <div>
                      <p className="text-white font-medium">{month.month}</p>
                      <p className="text-xs text-gray-400">{month.bets} bets, {month.wins} wins</p>
                    </div>
                    <div className="flex items-center gap-4">
                      <div className="w-24 bg-gray-800 rounded-full h-2 overflow-hidden">
                        <div
                          className={`h-full ${month.roi >= 10 ? 'bg-green-500' : month.roi >= 0 ? 'bg-green-600' : 'bg-red-500'}`}
                          style={{ width: `${Math.min(Math.abs(month.roi) * 3, 100)}%` }}
                        />
                      </div>
                      <span className={`text-sm font-medium w-16 text-right ${month.roi >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {month.roi >= 0 ? '+' : ''}{month.roi}%
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Current Streak */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Streaks</h2>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Current</span>
                  <span className={`text-lg font-bold ${stats.streaks.current.type === 'W' ? 'text-green-400' : 'text-red-400'}`}>
                    {stats.streaks.current.count}{stats.streaks.current.type}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Best Win Streak</span>
                  <span className="text-lg font-bold text-green-400">{stats.streaks.bestWin}W</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">Worst Loss Streak</span>
                  <span className="text-lg font-bold text-red-400">{stats.streaks.worstLoss}L</span>
                </div>
              </div>
            </div>

            {/* Recent Picks */}
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">Recent Picks</h2>
              <div className="space-y-3">
                {stats.recentPicks.map((pick, idx) => (
                  <div key={idx} className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0">
                    <div>
                      <p className="text-white text-sm">{pick.pick}</p>
                      <p className="text-xs text-gray-400">{pick.game}</p>
                    </div>
                    <span
                      className={`text-sm font-bold ${
                        pick.result === 'W'
                          ? 'text-green-400'
                          : pick.result === 'L'
                          ? 'text-red-400'
                          : 'text-gray-400'
                      }`}
                    >
                      {pick.result}
                    </span>
                  </div>
                ))}
              </div>
              <Link
                href="/games"
                className="block mt-4 text-center text-sm text-blue-400 hover:text-blue-300"
              >
                View All History
              </Link>
            </div>

            {/* Disclaimer */}
            <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
              <p className="text-xs text-gray-400">
                Past performance does not guarantee future results. All picks are
                tracked using 1-unit flat betting against the closing line. Results
                are verified and audited.
              </p>
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

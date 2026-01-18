import Link from 'next/link';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

// Demo tournament teams (Top 16 seeds typical for March Madness)
const DEMO_BRACKET = {
  regions: [
    {
      name: 'East',
      teams: [
        { seed: 1, name: 'UConn', record: '28-3', rank: 1 },
        { seed: 2, name: 'Marquette', record: '25-6', rank: 5 },
        { seed: 3, name: 'Creighton', record: '24-8', rank: 11 },
        { seed: 4, name: 'Duke', record: '24-7', rank: 9 },
      ],
    },
    {
      name: 'West',
      teams: [
        { seed: 1, name: 'Houston', record: '29-3', rank: 2 },
        { seed: 2, name: 'Arizona', record: '25-6', rank: 4 },
        { seed: 3, name: 'Baylor', record: '23-8', rank: 8 },
        { seed: 4, name: 'Alabama', record: '22-9', rank: 10 },
      ],
    },
    {
      name: 'South',
      teams: [
        { seed: 1, name: 'Purdue', record: '29-3', rank: 3 },
        { seed: 2, name: 'Tennessee', record: '24-7', rank: 6 },
        { seed: 3, name: 'Kentucky', record: '23-8', rank: 14 },
        { seed: 4, name: 'Kansas', record: '22-9', rank: 7 },
      ],
    },
    {
      name: 'Midwest',
      teams: [
        { seed: 1, name: 'North Carolina', record: '26-6', rank: 12 },
        { seed: 2, name: 'Iowa State', record: '26-6', rank: 13 },
        { seed: 3, name: 'Illinois', record: '24-8', rank: 15 },
        { seed: 4, name: 'Auburn', record: '24-7', rank: 16 },
      ],
    },
  ],
};

const KEY_DATES = [
  { date: 'March 17', event: 'Selection Sunday', status: 'upcoming' },
  { date: 'March 19-20', event: 'First Four', status: 'upcoming' },
  { date: 'March 21-22', event: 'Round of 64', status: 'upcoming' },
  { date: 'March 23-24', event: 'Round of 32', status: 'upcoming' },
  { date: 'March 28-29', event: 'Sweet 16', status: 'upcoming' },
  { date: 'March 30-31', event: 'Elite Eight', status: 'upcoming' },
  { date: 'April 5', event: 'Final Four', status: 'upcoming' },
  { date: 'April 7', event: 'National Championship', status: 'upcoming' },
];

async function getTournamentTeams() {
  if (!isSupabaseConfigured()) {
    return DEMO_BRACKET;
  }

  // In a real scenario, we'd fetch actual tournament bracket data
  // For now, return demo data
  return DEMO_BRACKET;
}

export default async function MarchMadnessPage() {
  const bracket = await getTournamentTeams();
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
                className="text-white font-medium"
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
              Demo Mode - Showing projected bracket based on current rankings
            </p>
          </div>
        </div>
      )}

      {/* Hero Section */}
      <div className="bg-gradient-to-b from-orange-900/20 to-black border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 py-12">
          <h1 className="text-4xl font-bold text-white mb-2">
            March Madness 2025
          </h1>
          <p className="text-xl text-gray-400 mb-6">
            NCAA Tournament Betting Analysis & Predictions
          </p>
          <div className="flex gap-4">
            <div className="bg-orange-500/20 border border-orange-500/30 rounded-lg px-4 py-2">
              <span className="text-orange-400 font-semibold">68 Teams</span>
            </div>
            <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg px-4 py-2">
              <span className="text-blue-400 font-semibold">67 Games</span>
            </div>
            <div className="bg-green-500/20 border border-green-500/30 rounded-lg px-4 py-2">
              <span className="text-green-400 font-semibold">AI Analysis for Every Matchup</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column - Key Dates */}
          <div className="lg:col-span-1">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 sticky top-4">
              <h2 className="text-lg font-semibold text-white mb-4">
                Key Dates
              </h2>
              <div className="space-y-3">
                {KEY_DATES.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
                  >
                    <div>
                      <p className="text-white font-medium">{item.event}</p>
                      <p className="text-sm text-gray-400">{item.date}</p>
                    </div>
                    <span className="text-xs px-2 py-1 bg-yellow-500/20 text-yellow-400 rounded">
                      Upcoming
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-6 pt-4 border-t border-gray-800">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">
                  Tournament Stats (Historical)
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Avg Upsets (12+ seeds)</span>
                    <span className="text-white">2.3/year</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">1-seeds winning title</span>
                    <span className="text-white">60%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">12 vs 5 seed upsets</span>
                    <span className="text-white">35%</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Bracket Preview */}
          <div className="lg:col-span-2">
            <h2 className="text-xl font-semibold text-white mb-6">
              Projected Bracket (Top Seeds by Region)
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {bracket.regions.map((region) => (
                <div
                  key={region.name}
                  className="bg-gray-900 border border-gray-800 rounded-lg p-4"
                >
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <span
                      className={`w-3 h-3 rounded-full ${
                        region.name === 'East'
                          ? 'bg-blue-500'
                          : region.name === 'West'
                          ? 'bg-red-500'
                          : region.name === 'South'
                          ? 'bg-green-500'
                          : 'bg-yellow-500'
                      }`}
                    />
                    {region.name} Region
                  </h3>
                  <div className="space-y-2">
                    {region.teams.map((team) => (
                      <div
                        key={team.name}
                        className="flex items-center justify-between p-3 bg-gray-800/50 rounded-lg hover:bg-gray-800 transition-colors cursor-pointer"
                      >
                        <div className="flex items-center gap-3">
                          <span className="w-6 h-6 flex items-center justify-center bg-gray-700 rounded text-xs font-bold">
                            {team.seed}
                          </span>
                          <div>
                            <p className="text-white font-medium">{team.name}</p>
                            <p className="text-xs text-gray-400">{team.record}</p>
                          </div>
                        </div>
                        {team.rank && (
                          <span className="text-xs px-2 py-1 bg-orange-500/20 text-orange-400 rounded">
                            #{team.rank}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            {/* Analysis Section */}
            <div className="mt-8 bg-gray-900 border border-gray-800 rounded-lg p-6">
              <h2 className="text-lg font-semibold text-white mb-4">
                AI Tournament Preview
              </h2>
              <div className="prose prose-invert max-w-none">
                <p className="text-gray-300 mb-4">
                  Our AI analysis will provide game-by-game breakdowns once the bracket is set.
                  Key factors we analyze for tournament games:
                </p>
                <ul className="text-gray-400 space-y-2">
                  <li>
                    <strong className="text-white">Seed matchup history</strong> -
                    Historical performance of seed combinations (e.g., 5 vs 12 upsets)
                  </li>
                  <li>
                    <strong className="text-white">Tournament experience</strong> -
                    Teams and coaches with deep March runs
                  </li>
                  <li>
                    <strong className="text-white">Conference tournament momentum</strong> -
                    Recent performance heading into the Big Dance
                  </li>
                  <li>
                    <strong className="text-white">Matchup-specific edges</strong> -
                    Style of play, pace, and defensive efficiency matchups
                  </li>
                </ul>
              </div>

              <div className="mt-6 flex gap-4">
                <button className="px-4 py-2 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors">
                  Get Notified at Selection Sunday
                </button>
                <button className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors">
                  View Historical Analysis
                </button>
              </div>
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

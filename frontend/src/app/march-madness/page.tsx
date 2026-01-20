import Link from 'next/link';

const KEY_DATES = [
  { date: 'March 16', event: 'Selection Sunday' },
  { date: 'March 18-19', event: 'First Four' },
  { date: 'March 20-21', event: 'Round of 64' },
  { date: 'March 22-23', event: 'Round of 32' },
  { date: 'March 27-28', event: 'Sweet 16' },
  { date: 'March 29-30', event: 'Elite Eight' },
  { date: 'April 5', event: 'Final Four' },
  { date: 'April 7', event: 'National Championship' },
];

export default function MarchMadnessPage() {
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
          </div>
        </div>
      </header>

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
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
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
            </div>
          </div>

          {/* Right Column - Coming Soon */}
          <div className="lg:col-span-2">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
              <h2 className="text-2xl font-bold text-white mb-4">
                Bracket Analysis Coming Soon
              </h2>
              <p className="text-gray-400 mb-6 max-w-lg mx-auto">
                Once the bracket is announced on Selection Sunday, we'll provide AI-powered analysis
                for every matchup including upset predictions, value picks, and round-by-round breakdowns.
              </p>

              <div className="bg-gray-800/50 rounded-lg p-6 text-left max-w-md mx-auto mb-6">
                <h3 className="text-white font-semibold mb-3">What to expect:</h3>
                <ul className="text-gray-400 space-y-2">
                  <li>- Claude + Grok AI analysis for each game</li>
                  <li>- Upset probability ratings</li>
                  <li>- KenPom + Haslametrics matchup data</li>
                  <li>- Historical seed performance trends</li>
                  <li>- Best value bets by round</li>
                </ul>
              </div>

              <Link
                href="/"
                className="inline-block px-6 py-3 bg-orange-600 hover:bg-orange-700 text-white rounded-lg transition-colors"
              >
                View Today's Games
              </Link>
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

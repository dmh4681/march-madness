import Link from 'next/link';

export default function PerformancePage() {
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
              <Link href="/march-madness" className="text-gray-400 hover:text-white transition-colors">
                March Madness
              </Link>
              <Link href="/performance" className="text-white font-medium">
                Performance
              </Link>
            </nav>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-16">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white mb-4">Performance Tracking</h1>
          <p className="text-xl text-gray-400 mb-8">Coming Soon</p>

          <div className="max-w-md mx-auto bg-gray-900 border border-gray-800 rounded-lg p-8">
            <p className="text-gray-300 mb-6">
              We're building a comprehensive performance dashboard to track:
            </p>
            <ul className="text-left text-gray-400 space-y-3 mb-8">
              <li className="flex items-center gap-2">
                <span className="text-green-400">-</span>
                Season ROI and win rate
              </li>
              <li className="flex items-center gap-2">
                <span className="text-green-400">-</span>
                Performance by confidence tier
              </li>
              <li className="flex items-center gap-2">
                <span className="text-green-400">-</span>
                AI model accuracy (Claude vs Grok)
              </li>
              <li className="flex items-center gap-2">
                <span className="text-green-400">-</span>
                Historical pick results
              </li>
            </ul>

            <Link
              href="/"
              className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              Back to Dashboard
            </Link>
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

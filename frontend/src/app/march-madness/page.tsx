'use client';

import { useState } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

const KEY_DATES = [
  { date: 'March 16', event: 'Selection Sunday', shortEvent: 'Selection' },
  { date: 'March 18-19', event: 'First Four', shortEvent: 'First Four' },
  { date: 'March 20-21', event: 'Round of 64', shortEvent: 'Rd of 64' },
  { date: 'March 22-23', event: 'Round of 32', shortEvent: 'Rd of 32' },
  { date: 'March 27-28', event: 'Sweet 16', shortEvent: 'Sweet 16' },
  { date: 'March 29-30', event: 'Elite Eight', shortEvent: 'Elite 8' },
  { date: 'April 5', event: 'Final Four', shortEvent: 'Final 4' },
  { date: 'April 7', event: 'National Championship', shortEvent: 'Title Game' },
];

export default function MarchMadnessPage() {
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

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

      {/* Hero Section - responsive */}
      <div className="bg-gradient-to-b from-orange-900/20 to-black border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-6 sm:py-12">
          <h1 className="text-2xl sm:text-4xl font-bold text-white mb-1 sm:mb-2">
            March Madness 2025
          </h1>
          <p className="text-base sm:text-xl text-gray-400 mb-4 sm:mb-6">
            NCAA Tournament Analysis
          </p>
          {/* Stats badges - horizontally scrollable on mobile */}
          <div className="flex gap-2 sm:gap-4 overflow-x-auto pb-2 sm:pb-0 scrollbar-hide -mx-3 px-3 sm:mx-0 sm:px-0">
            <div className="bg-orange-500/20 border border-orange-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0">
              <span className="text-orange-400 font-semibold text-sm sm:text-base">68 Teams</span>
            </div>
            <div className="bg-blue-500/20 border border-blue-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0">
              <span className="text-blue-400 font-semibold text-sm sm:text-base">67 Games</span>
            </div>
            <div className="bg-green-500/20 border border-green-500/30 rounded-lg px-3 sm:px-4 py-2 shrink-0 whitespace-nowrap">
              <span className="text-green-400 font-semibold text-sm sm:text-base">AI Analysis</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        {/* Mobile: Region selector tabs for when bracket is live */}
        <div className="sm:hidden mb-4 -mx-3 px-3">
          <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
            {['All', 'East', 'West', 'South', 'Midwest'].map((region) => (
              <button
                key={region}
                type="button"
                onClick={() => setSelectedRegion(region === 'All' ? null : region)}
                className={cn(
                  "px-4 py-2 min-h-[44px] text-sm font-medium rounded-lg shrink-0 transition-colors",
                  (selectedRegion === region || (region === 'All' && !selectedRegion))
                    ? "bg-orange-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                )}
              >
                {region}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-8">
          {/* Key Dates - horizontal scroll on mobile, vertical list on desktop */}
          <div className="lg:col-span-1 order-2 lg:order-1">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-6">
              <h2 className="text-base sm:text-lg font-semibold text-white mb-3 sm:mb-4">
                Key Dates
              </h2>
              {/* Mobile: Horizontal scroll */}
              <div className="sm:hidden overflow-x-auto -mx-4 px-4">
                <div className="flex gap-3 pb-2 scrollbar-hide min-w-max">
                  {KEY_DATES.map((item, idx) => (
                    <div
                      key={idx}
                      className="bg-gray-800/50 rounded-lg p-3 min-w-[140px] shrink-0"
                    >
                      <p className="text-white font-medium text-sm">{item.shortEvent}</p>
                      <p className="text-xs text-gray-400">{item.date}</p>
                    </div>
                  ))}
                </div>
              </div>
              {/* Desktop: Vertical list */}
              <div className="hidden sm:block space-y-3">
                {KEY_DATES.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between py-2 border-b border-gray-800 last:border-0"
                  >
                    <div>
                      <p className="text-white font-medium">{item.event}</p>
                      <p className="text-sm text-gray-400">{item.date}</p>
                    </div>
                    <span className="text-xs px-2.5 py-1 min-h-[32px] flex items-center bg-yellow-500/20 text-yellow-400 rounded">
                      Upcoming
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Coming Soon / Bracket Placeholder */}
          {/* TODO: When bracket becomes functional, implement zoom/pan controls:
              - Use react-zoom-pan-pinch library for touch gestures
              - Add zoom in/out buttons for accessibility
              - Implement double-tap to zoom on mobile
              - Add reset zoom button
              - Consider using transform-origin for smooth zooming */}
          <div className="lg:col-span-2 order-1 lg:order-2">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 sm:p-8">
              {/* Bracket placeholder with pinch-to-zoom hint */}
              <div className="text-center">
                <h2 className="text-xl sm:text-2xl font-bold text-white mb-2 sm:mb-4">
                  Bracket Analysis Coming Soon
                </h2>
                <p className="text-sm sm:text-base text-gray-400 mb-4 sm:mb-6 max-w-lg mx-auto">
                  Once the bracket is announced on Selection Sunday, we'll provide AI-powered analysis
                  for every matchup.
                </p>

                {/* Mobile hint for future bracket interaction */}
                <div className="sm:hidden mb-4 p-3 bg-gray-800/50 rounded-lg border border-gray-700">
                  <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                    </svg>
                    <span>Pinch to zoom when bracket is live</span>
                  </div>
                </div>

                <div className="bg-gray-800/50 rounded-lg p-4 sm:p-6 text-left max-w-md mx-auto mb-4 sm:mb-6">
                  <h3 className="text-white font-semibold mb-2 sm:mb-3 text-sm sm:text-base">What to expect:</h3>
                  <ul className="text-gray-400 space-y-1.5 sm:space-y-2 text-sm">
                    <li className="flex items-start gap-2">
                      <span className="text-orange-400 mt-0.5">•</span>
                      Claude + Grok AI analysis
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-orange-400 mt-0.5">•</span>
                      Upset probability ratings
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-orange-400 mt-0.5">•</span>
                      KenPom + Haslametrics matchup data
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-orange-400 mt-0.5">•</span>
                      Historical seed trends
                    </li>
                    <li className="flex items-start gap-2">
                      <span className="text-orange-400 mt-0.5">•</span>
                      Best value bets by round
                    </li>
                  </ul>
                </div>

                <Link
                  href="/"
                  className="inline-flex items-center justify-center px-5 sm:px-6 py-3 min-h-[48px] bg-orange-600 hover:bg-orange-700 active:bg-orange-800 text-white rounded-lg transition-colors text-sm sm:text-base font-medium"
                >
                  View Today's Games
                </Link>
              </div>
            </div>
          </div>
        </div>
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

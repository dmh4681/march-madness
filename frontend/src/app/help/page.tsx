/**
 * Help & Documentation Page
 * =========================
 *
 * Comprehensive user guide for understanding Conference Contrarian's
 * betting analysis, terminology, and how to interpret AI recommendations.
 *
 * This page serves as a reference for:
 * - Betting terminology (spreads, moneylines, totals)
 * - Advanced analytics (KenPom, Haslametrics)
 * - Confidence tier interpretation
 * - AI analysis understanding
 * - Bankroll management basics
 */

import { Metadata } from 'next';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'Help & Documentation | Conference Contrarian',
  description: 'Learn about betting terminology, KenPom ratings, Haslametrics analytics, and how to interpret AI analysis results.',
};

export default function HelpPage() {
  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-4xl mx-auto px-4 py-8 sm:py-12">
        {/* Header */}
        <div className="mb-8">
          <Link
            href="/"
            className="text-blue-400 hover:text-blue-300 text-sm mb-4 inline-block"
          >
            &larr; Back to Dashboard
          </Link>
          <h1 className="text-3xl sm:text-4xl font-bold mb-2">Help & Documentation</h1>
          <p className="text-gray-400">
            Everything you need to understand Conference Contrarian&apos;s betting analysis
          </p>
        </div>

        {/* Table of Contents */}
        <nav className="mb-12 p-4 bg-gray-900 rounded-lg border border-gray-800">
          <h2 className="font-semibold mb-3">Quick Navigation</h2>
          <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
            <li><a href="#betting-basics" className="text-blue-400 hover:underline">Betting Basics</a></li>
            <li><a href="#spreads" className="text-blue-400 hover:underline">Understanding Spreads</a></li>
            <li><a href="#moneylines" className="text-blue-400 hover:underline">Moneyline Betting</a></li>
            <li><a href="#totals" className="text-blue-400 hover:underline">Over/Under Totals</a></li>
            <li><a href="#kenpom" className="text-blue-400 hover:underline">KenPom Ratings</a></li>
            <li><a href="#haslametrics" className="text-blue-400 hover:underline">Haslametrics Analytics</a></li>
            <li><a href="#confidence" className="text-blue-400 hover:underline">Confidence Tiers</a></li>
            <li><a href="#ai-analysis" className="text-blue-400 hover:underline">AI Analysis</a></li>
            <li><a href="#edge" className="text-blue-400 hover:underline">Understanding Edge</a></li>
            <li><a href="#bankroll" className="text-blue-400 hover:underline">Bankroll Management</a></li>
          </ul>
        </nav>

        {/* Betting Basics */}
        <section id="betting-basics" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Betting Basics</h2>
          <p className="text-gray-300 mb-4">
            Sports betting involves wagering money on the outcome of sporting events.
            Understanding the fundamental concepts is essential before placing any bets.
          </p>
          <div className="bg-gray-900 p-4 rounded-lg border border-gray-800 mb-4">
            <h3 className="font-semibold text-yellow-400 mb-2">The Vig (Juice)</h3>
            <p className="text-gray-300 text-sm mb-2">
              Sportsbooks charge a commission called the &quot;vig&quot; or &quot;juice&quot;. Standard odds
              are -110, meaning you risk $110 to win $100.
            </p>
            <p className="text-gray-400 text-sm">
              <strong>Breakeven win rate at -110:</strong> 110 / (110 + 100) = <span className="text-green-400">52.4%</span>
            </p>
            <p className="text-gray-400 text-sm mt-2">
              You must win more than 52.4% of your bets to be profitable long-term.
            </p>
          </div>
        </section>

        {/* Spreads */}
        <section id="spreads" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Understanding Spreads</h2>
          <p className="text-gray-300 mb-4">
            The point spread is the most common way to bet on basketball. It levels the
            playing field by giving the underdog a head start.
          </p>

          <div className="grid md:grid-cols-2 gap-4 mb-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-orange-400 mb-2">Favorite (-)</h3>
              <p className="text-gray-300 text-sm mb-2">
                The team expected to win. They must win by MORE than the spread.
              </p>
              <div className="text-sm bg-gray-800 p-2 rounded">
                <p className="text-gray-400">Example: Duke -7.5</p>
                <p className="text-gray-300">Duke must win by 8+ points to cover</p>
              </div>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-blue-400 mb-2">Underdog (+)</h3>
              <p className="text-gray-300 text-sm mb-2">
                The team expected to lose. They can lose by LESS than the spread and still cover.
              </p>
              <div className="text-sm bg-gray-800 p-2 rounded">
                <p className="text-gray-400">Example: UNC +7.5</p>
                <p className="text-gray-300">UNC wins or loses by 7 or less to cover</p>
              </div>
            </div>
          </div>

          <div className="bg-blue-500/10 border border-blue-500/30 p-4 rounded-lg">
            <h3 className="font-semibold text-blue-400 mb-2">Conference Contrarian Strategy</h3>
            <p className="text-gray-300 text-sm">
              Our analysis focuses on conference games where a ranked team faces an unranked opponent.
              Historical data suggests that unranked home underdogs in these situations cover at a
              higher rate than the market implies, creating potential value.
            </p>
          </div>
        </section>

        {/* Moneylines */}
        <section id="moneylines" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Moneyline Betting</h2>
          <p className="text-gray-300 mb-4">
            Moneyline bets are simply picking which team will win, regardless of margin.
            Odds indicate the payout ratio.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-sm mb-4">
              <thead>
                <tr className="border-b border-gray-800">
                  <th className="text-left py-2 text-gray-400">Odds</th>
                  <th className="text-left py-2 text-gray-400">Meaning</th>
                  <th className="text-left py-2 text-gray-400">To Win $100</th>
                  <th className="text-left py-2 text-gray-400">Implied Probability</th>
                </tr>
              </thead>
              <tbody className="text-gray-300">
                <tr className="border-b border-gray-800">
                  <td className="py-2 text-red-400">-200</td>
                  <td className="py-2">Heavy favorite</td>
                  <td className="py-2">Risk $200</td>
                  <td className="py-2">66.7%</td>
                </tr>
                <tr className="border-b border-gray-800">
                  <td className="py-2 text-orange-400">-150</td>
                  <td className="py-2">Moderate favorite</td>
                  <td className="py-2">Risk $150</td>
                  <td className="py-2">60%</td>
                </tr>
                <tr className="border-b border-gray-800">
                  <td className="py-2 text-yellow-400">-110</td>
                  <td className="py-2">Slight favorite</td>
                  <td className="py-2">Risk $110</td>
                  <td className="py-2">52.4%</td>
                </tr>
                <tr className="border-b border-gray-800">
                  <td className="py-2 text-green-400">+150</td>
                  <td className="py-2">Moderate underdog</td>
                  <td className="py-2">Risk $67</td>
                  <td className="py-2">40%</td>
                </tr>
                <tr className="border-b border-gray-800">
                  <td className="py-2 text-green-400">+300</td>
                  <td className="py-2">Big underdog</td>
                  <td className="py-2">Risk $33</td>
                  <td className="py-2">25%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
            <h3 className="font-semibold mb-2">Implied Probability Formula</h3>
            <div className="text-sm text-gray-300 space-y-2">
              <p><strong>For negative odds:</strong> |odds| / (|odds| + 100) &times; 100%</p>
              <p><strong>For positive odds:</strong> 100 / (odds + 100) &times; 100%</p>
            </div>
          </div>
        </section>

        {/* Totals */}
        <section id="totals" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Over/Under Totals</h2>
          <p className="text-gray-300 mb-4">
            Totals betting involves predicting whether the combined score of both teams
            will be over or under a set number.
          </p>

          <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
            <h3 className="font-semibold mb-2">Example: Duke vs UNC - Total 147.5</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <p className="text-green-400 font-semibold">OVER 147.5</p>
                <p className="text-gray-300">Combined score of 148+ wins</p>
                <p className="text-gray-400">Example: 85-72 = 157 &check;</p>
              </div>
              <div>
                <p className="text-red-400 font-semibold">UNDER 147.5</p>
                <p className="text-gray-300">Combined score of 147 or less wins</p>
                <p className="text-gray-400">Example: 68-65 = 133 &check;</p>
              </div>
            </div>
          </div>
        </section>

        {/* KenPom */}
        <section id="kenpom" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">KenPom Ratings</h2>
          <p className="text-gray-300 mb-4">
            KenPom.com is the gold standard for college basketball analytics, created by
            Ken Pomeroy. These tempo-adjusted efficiency metrics are widely used by
            coaches, media, and bettors.
          </p>

          <div className="space-y-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-yellow-400 mb-2">Adjusted Efficiency Margin (AdjEM)</h3>
              <p className="text-gray-300 text-sm mb-2">
                The main power rating. Represents the expected point differential per 100 possessions
                against an average D-I team on a neutral court.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Formula:</strong> AdjEM = AdjO - AdjD
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Interpretation:</strong> +20 means expected to outscore average team by 20 points per 100 possessions
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-green-400 mb-2">Adjusted Offensive Efficiency (AdjO)</h3>
              <p className="text-gray-300 text-sm mb-2">
                Points scored per 100 possessions, adjusted for opponent quality.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Elite:</strong> 120+ | <strong>Good:</strong> 110-120 | <strong>Average:</strong> 100-110
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-blue-400 mb-2">Adjusted Defensive Efficiency (AdjD)</h3>
              <p className="text-gray-300 text-sm mb-2">
                Points allowed per 100 possessions, adjusted for opponent quality.
                <strong className="text-yellow-400"> Lower is better!</strong>
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Elite:</strong> &lt;95 | <strong>Good:</strong> 95-100 | <strong>Average:</strong> 100-105
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-purple-400 mb-2">Tempo (AdjT)</h3>
              <p className="text-gray-300 text-sm mb-2">
                Average possessions per 40 minutes. High tempo = more possessions = more variance.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Fast:</strong> 72+ | <strong>Average:</strong> 67-72 | <strong>Slow:</strong> &lt;67
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-orange-400 mb-2">Luck</h3>
              <p className="text-gray-300 text-sm mb-2">
                How much a team&apos;s record deviates from what their efficiency metrics predict.
                High luck = regression candidate.
              </p>
              <p className="text-gray-400 text-sm">
                Positive luck means the team has won more close games than expected.
                These teams often regress to their underlying quality.
              </p>
            </div>
          </div>
        </section>

        {/* Haslametrics */}
        <section id="haslametrics" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Haslametrics Analytics</h2>
          <p className="text-gray-300 mb-4">
            Haslametrics uses the &quot;All-Play&quot; methodology - simulating how teams would perform
            against every other D-I team. It&apos;s free and provides unique insights.
          </p>

          <div className="space-y-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-green-400 mb-2">All-Play Percentage</h3>
              <p className="text-gray-300 text-sm mb-2">
                The probability of beating an average D-I team on a neutral court.
                This is the core Haslametrics ranking metric.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Elite:</strong> 90%+ | <strong>Tournament:</strong> 75-90% | <strong>Bubble:</strong> 60-75%
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-yellow-400 mb-2">Momentum Indicators</h3>
              <p className="text-gray-300 text-sm mb-2">
                Tracks recent performance trends. Positive momentum means the team is playing
                better than their season average.
              </p>
              <div className="text-gray-400 text-sm">
                <p><strong>Overall Momentum:</strong> Combined offensive and defensive trends</p>
                <p><strong>Offensive Momentum:</strong> Scoring trend direction</p>
                <p><strong>Defensive Momentum:</strong> Defensive performance trend</p>
              </div>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-blue-400 mb-2">Quadrant Records</h3>
              <p className="text-gray-300 text-sm mb-2">
                Performance broken down by opponent quality (NET rankings):
              </p>
              <div className="text-gray-400 text-sm">
                <p><strong>Q1:</strong> Home vs 1-30, Neutral vs 1-50, Away vs 1-75</p>
                <p><strong>Q2:</strong> Home vs 31-75, Neutral vs 51-100, Away vs 76-135</p>
                <p><strong>Q3:</strong> Home vs 76-160, Neutral vs 101-200, Away vs 136-240</p>
                <p><strong>Q4:</strong> Home vs 161+, Neutral vs 201+, Away vs 241+</p>
              </div>
              <p className="text-gray-300 text-sm mt-2">
                Strong Q1 records indicate true tournament quality.
              </p>
            </div>
          </div>
        </section>

        {/* Confidence Tiers */}
        <section id="confidence" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Confidence Tiers</h2>
          <p className="text-gray-300 mb-4">
            Our model assigns confidence tiers based on the predicted edge over fair market odds.
          </p>

          <div className="grid gap-4">
            <div className="bg-green-500/10 border border-green-500/30 p-4 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">&#128293;</span>
                <h3 className="font-semibold text-green-400">HIGH Confidence</h3>
              </div>
              <p className="text-gray-300 text-sm mb-2">
                Edge &gt; 4% over implied odds. Strong conviction pick.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Win probability:</strong> ~54-60%<br />
                <strong>Expected ROI:</strong> +5% to +14%<br />
                <strong>Suggested bet:</strong> 1.5-2 units
              </p>
            </div>

            <div className="bg-yellow-500/10 border border-yellow-500/30 p-4 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">&#9889;</span>
                <h3 className="font-semibold text-yellow-400">MEDIUM Confidence</h3>
              </div>
              <p className="text-gray-300 text-sm mb-2">
                Edge 2-4% over implied odds. Solid value exists.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Win probability:</strong> ~52-54%<br />
                <strong>Expected ROI:</strong> +1% to +5%<br />
                <strong>Suggested bet:</strong> 1 unit
              </p>
            </div>

            <div className="bg-orange-500/10 border border-orange-500/30 p-4 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">&#128202;</span>
                <h3 className="font-semibold text-orange-400">LOW Confidence</h3>
              </div>
              <p className="text-gray-300 text-sm mb-2">
                Edge &lt; 2%. Marginal value, proceed with caution.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Win probability:</strong> ~50-52%<br />
                <strong>Expected ROI:</strong> -3% to +1%<br />
                <strong>Suggested bet:</strong> 0.5 units or pass
              </p>
            </div>

            <div className="bg-gray-500/10 border border-gray-500/30 p-4 rounded-lg">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xl">&#9208;&#65039;</span>
                <h3 className="font-semibold text-gray-400">PASS</h3>
              </div>
              <p className="text-gray-300 text-sm mb-2">
                No edge detected. Skip this game.
              </p>
              <p className="text-gray-400 text-sm">
                <strong>Win probability:</strong> ~50%<br />
                <strong>Expected ROI:</strong> -4.5% (the vig)<br />
                <strong>Suggested bet:</strong> No bet
              </p>
            </div>
          </div>
        </section>

        {/* AI Analysis */}
        <section id="ai-analysis" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Understanding AI Analysis</h2>
          <p className="text-gray-300 mb-4">
            We use two AI providers - Claude (Anthropic) and Grok (xAI) - to provide
            independent analysis perspectives.
          </p>

          <div className="space-y-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-orange-500/30">
              <h3 className="font-semibold text-orange-400 mb-2">Claude (Anthropic)</h3>
              <p className="text-gray-300 text-sm">
                Our primary AI provider. Known for thorough, nuanced analysis with
                careful consideration of multiple factors.
              </p>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-blue-500/30">
              <h3 className="font-semibold text-blue-400 mb-2">Grok (xAI)</h3>
              <p className="text-gray-300 text-sm">
                Alternative perspective. Good for comparison and identifying
                factors one model might emphasize more than the other.
              </p>
            </div>

            <div className="bg-purple-500/10 border border-purple-500/30 p-4 rounded-lg">
              <h3 className="font-semibold text-purple-400 mb-2">AI Consensus</h3>
              <p className="text-gray-300 text-sm mb-2">
                When both AI providers agree on the same bet, confidence increases.
              </p>
              <div className="text-gray-400 text-sm">
                <p><strong>Both agree on bet:</strong> Higher conviction</p>
                <p><strong>Both recommend pass:</strong> Likely no edge</p>
                <p><strong>Split decision:</strong> Use caution, investigate further</p>
              </div>
            </div>
          </div>

          <div className="mt-4 bg-gray-900 p-4 rounded-lg border border-gray-800">
            <h3 className="font-semibold mb-2">AI Receives This Data:</h3>
            <ul className="text-gray-300 text-sm space-y-1">
              <li>&bull; Team rankings and conference info</li>
              <li>&bull; Current betting lines (spread, ML, total)</li>
              <li>&bull; KenPom metrics (if available)</li>
              <li>&bull; Haslametrics data (if available)</li>
              <li>&bull; Prediction market prices (when available)</li>
              <li>&bull; Home court and venue information</li>
            </ul>
          </div>
        </section>

        {/* Edge */}
        <section id="edge" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Understanding Edge</h2>
          <p className="text-gray-300 mb-4">
            &quot;Edge&quot; refers to your advantage over the betting market. It&apos;s the difference
            between your estimated probability and the market&apos;s implied probability.
          </p>

          <div className="bg-gray-900 p-4 rounded-lg border border-gray-800 mb-4">
            <h3 className="font-semibold mb-2">Edge Calculation</h3>
            <div className="text-sm text-gray-300 space-y-2">
              <p><strong>Simple Edge:</strong> Your P(win) - 0.50</p>
              <p><strong>vs Market:</strong> Your P(win) - Market Implied P(win)</p>
            </div>
            <div className="mt-3 bg-gray-800 p-3 rounded text-sm">
              <p className="text-gray-400">Example:</p>
              <p className="text-gray-300">Model predicts: 56% chance underdog covers</p>
              <p className="text-gray-300">Market implies: 50% (at -110 odds)</p>
              <p className="text-green-400">Edge: 56% - 50% = 6% edge</p>
            </div>
          </div>

          <div className="bg-yellow-500/10 border border-yellow-500/30 p-4 rounded-lg">
            <h3 className="font-semibold text-yellow-400 mb-2">Important Caveat</h3>
            <p className="text-gray-300 text-sm">
              Model edges are estimates based on historical patterns. They don&apos;t guarantee
              wins. Even with a true 55% edge, you can have losing streaks. Focus on making
              good decisions, not individual outcomes.
            </p>
          </div>
        </section>

        {/* Bankroll Management */}
        <section id="bankroll" className="mb-12">
          <h2 className="text-2xl font-bold mb-4 pb-2 border-b border-gray-800">Bankroll Management</h2>
          <p className="text-gray-300 mb-4">
            Proper bankroll management is essential for long-term success. Even winning
            bettors can go broke without discipline.
          </p>

          <div className="space-y-4">
            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-green-400 mb-2">The Unit System</h3>
              <p className="text-gray-300 text-sm mb-2">
                A &quot;unit&quot; is a standardized bet size, typically 1-2% of your total bankroll.
              </p>
              <div className="text-gray-400 text-sm">
                <p><strong>$1,000 bankroll:</strong> 1 unit = $10-$20</p>
                <p><strong>$5,000 bankroll:</strong> 1 unit = $50-$100</p>
              </div>
            </div>

            <div className="bg-gray-900 p-4 rounded-lg border border-gray-800">
              <h3 className="font-semibold text-blue-400 mb-2">Kelly Criterion</h3>
              <p className="text-gray-300 text-sm mb-2">
                Mathematical formula for optimal bet sizing based on edge:
              </p>
              <p className="text-gray-400 text-sm font-mono">
                f* = (bp - q) / b
              </p>
              <p className="text-gray-400 text-sm mt-2">
                Where b = odds ratio, p = win probability, q = lose probability
              </p>
              <p className="text-yellow-400 text-sm mt-2">
                Most bettors use &quot;half Kelly&quot; or &quot;quarter Kelly&quot; for safety.
              </p>
            </div>

            <div className="bg-red-500/10 border border-red-500/30 p-4 rounded-lg">
              <h3 className="font-semibold text-red-400 mb-2">Warning Signs</h3>
              <ul className="text-gray-300 text-sm space-y-1">
                <li>&bull; Chasing losses with bigger bets</li>
                <li>&bull; Betting more than 5% of bankroll on one game</li>
                <li>&bull; Betting with money you can&apos;t afford to lose</li>
                <li>&bull; Increasing bet sizes after wins (&quot;house money&quot; fallacy)</li>
              </ul>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="pt-8 border-t border-gray-800 text-center text-gray-500 text-sm">
          <p className="mb-2">
            <strong>Disclaimer:</strong> Sports betting involves risk. Never bet more than you
            can afford to lose. Past performance does not guarantee future results.
          </p>
          <p>
            Questions? Contact us at{' '}
            <a href="mailto:support@confcontrarian.com" className="text-blue-400 hover:underline">
              support@confcontrarian.com
            </a>
          </p>
        </footer>
      </div>
    </main>
  );
}

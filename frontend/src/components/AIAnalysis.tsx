'use client';

import { useState } from 'react';
import type { AIAnalysis, AIProvider } from '@/lib/types';
import { AIAnalysisSkeleton, AICompareViewSkeleton } from './ui/skeleton';

type ViewMode = AIProvider | 'compare';

interface AIAnalysisProps {
  analyses: AIAnalysis[];
  onRequestAnalysis?: (provider: AIProvider) => Promise<void>;
  isLoading?: boolean;
}

export function AIAnalysisPanel({
  analyses,
  onRequestAnalysis,
  isLoading = false,
}: AIAnalysisProps) {
  const [activeView, setActiveView] = useState<ViewMode>('claude');

  const claudeAnalysis = analyses.find((a) => a.ai_provider === 'claude');
  const grokAnalysis = analyses.find((a) => a.ai_provider === 'grok');
  const hasBothAnalyses = claudeAnalysis && grokAnalysis;

  const activeAnalysis =
    activeView === 'claude' ? claudeAnalysis : activeView === 'grok' ? grokAnalysis : null;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Tab Header - touch-friendly on mobile */}
      <div className="flex border-b border-gray-800">
        <button
          onClick={() => setActiveView('claude')}
          className={`flex-1 px-3 sm:px-4 py-3 sm:py-3 min-h-[48px] text-sm font-medium transition-colors ${
            activeView === 'claude'
              ? 'bg-gray-800 text-white border-b-2 border-orange-500'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50 active:bg-gray-800'
          }`}
        >
          <span className="flex items-center justify-center gap-1.5 sm:gap-2">
            <ClaudeIcon />
            <span className="hidden sm:inline">Claude</span>
            <span className="sm:hidden">C</span>
            {claudeAnalysis && (
              <span className="text-xs text-green-400 hidden sm:inline">Ready</span>
            )}
            {claudeAnalysis && (
              <span className="w-2 h-2 rounded-full bg-green-400 sm:hidden" />
            )}
          </span>
        </button>
        <button
          onClick={() => setActiveView('grok')}
          className={`flex-1 px-3 sm:px-4 py-3 sm:py-3 min-h-[48px] text-sm font-medium transition-colors ${
            activeView === 'grok'
              ? 'bg-gray-800 text-white border-b-2 border-blue-500'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50 active:bg-gray-800'
          }`}
        >
          <span className="flex items-center justify-center gap-1.5 sm:gap-2">
            <GrokIcon />
            <span className="hidden sm:inline">Grok</span>
            <span className="sm:hidden">G</span>
            {grokAnalysis && (
              <span className="text-xs text-green-400 hidden sm:inline">Ready</span>
            )}
            {grokAnalysis && (
              <span className="w-2 h-2 rounded-full bg-green-400 sm:hidden" />
            )}
          </span>
        </button>
        {hasBothAnalyses && (
          <button
            onClick={() => setActiveView('compare')}
            className={`flex-1 px-3 sm:px-4 py-3 sm:py-3 min-h-[48px] text-sm font-medium transition-colors ${
              activeView === 'compare'
                ? 'bg-gray-800 text-white border-b-2 border-purple-500'
                : 'text-gray-400 hover:text-white hover:bg-gray-800/50 active:bg-gray-800'
            }`}
          >
            <span className="flex items-center justify-center gap-1.5 sm:gap-2">
              <CompareIcon />
              <span className="hidden sm:inline">Compare</span>
              <span className="sm:hidden">vs</span>
            </span>
          </button>
        )}
      </div>

      {/* Content - responsive padding */}
      <div className="p-4 sm:p-6">
        {isLoading ? (
          activeView === 'compare' ? (
            <AICompareViewSkeleton />
          ) : (
            <AIAnalysisSkeleton />
          )
        ) : activeView === 'compare' && hasBothAnalyses ? (
          <CompareView claude={claudeAnalysis} grok={grokAnalysis} />
        ) : activeAnalysis ? (
          <AnalysisContent analysis={activeAnalysis} />
        ) : (
          <div className="text-center py-6 sm:py-8">
            <p className="text-gray-400 mb-4 text-sm sm:text-base">
              No {activeView === 'claude' ? 'Claude' : 'Grok'} analysis
              available yet.
            </p>
            {onRequestAnalysis && (
              <button
                onClick={() => onRequestAnalysis(activeView as AIProvider)}
                className="px-4 py-2.5 min-h-[44px] bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white rounded-lg transition-colors"
              >
                Generate {activeView === 'claude' ? 'Claude' : 'Grok'}{' '}
                Analysis
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function CompareView({ claude, grok }: { claude: AIAnalysis; grok: AIAnalysis }) {
  const agreesOnBet = claude.recommended_bet === grok.recommended_bet;
  const avgConfidence = ((claude.confidence_score || 0) + (grok.confidence_score || 0)) / 2;

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Consensus Banner - responsive layout */}
      <div className={`p-3 sm:p-4 rounded-lg border ${
        agreesOnBet && claude.recommended_bet !== 'pass'
          ? 'bg-green-500/10 border-green-500/30'
          : agreesOnBet
          ? 'bg-gray-500/10 border-gray-500/30'
          : 'bg-yellow-500/10 border-yellow-500/30'
      }`}>
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="text-xl sm:text-2xl shrink-0">
            {agreesOnBet && claude.recommended_bet !== 'pass' ? '🎯' : agreesOnBet ? '⏸️' : '⚖️'}
          </div>
          <div className="flex-1 min-w-0">
            <div className={`text-xs sm:text-sm font-medium ${
              agreesOnBet && claude.recommended_bet !== 'pass'
                ? 'text-green-400'
                : agreesOnBet
                ? 'text-gray-400'
                : 'text-yellow-400'
            }`}>
              {agreesOnBet ? 'AI Consensus' : 'Split Decision'}
            </div>
            <div className="text-white font-semibold text-sm sm:text-base truncate">
              {agreesOnBet
                ? claude.recommended_bet === 'pass'
                  ? 'Both recommend passing'
                  : `Both: ${formatBetRecommendation(claude.recommended_bet || '')}`
                : 'Models disagree'}
            </div>
          </div>
          {agreesOnBet && claude.recommended_bet !== 'pass' && (
            <div className="text-right shrink-0">
              <div className="text-xl sm:text-2xl font-bold text-green-400">
                {(avgConfidence * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-gray-400 hidden sm:block">avg confidence</div>
            </div>
          )}
        </div>
      </div>

      {/* Side by Side Picks - stack on very small screens */}
      <div className="grid grid-cols-2 gap-2 sm:gap-4">
        {/* Claude */}
        <div className="p-3 sm:p-4 bg-gray-800/50 rounded-lg border border-orange-500/30">
          <div className="flex items-center gap-1.5 sm:gap-2 mb-2 sm:mb-3">
            <ClaudeIcon />
            <span className="font-medium text-white text-sm sm:text-base">Claude</span>
          </div>
          <div className="space-y-1.5 sm:space-y-2">
            <div>
              <span className="text-xs text-gray-400">Pick:</span>
              <div className="text-white font-medium text-sm sm:text-base truncate">
                {claude.recommended_bet === 'pass' ? 'Pass' : formatBetRecommendation(claude.recommended_bet || '')}
              </div>
            </div>
            <div>
              <span className="text-xs text-gray-400">Confidence:</span>
              <div className="text-white font-medium text-sm sm:text-base">
                {((claude.confidence_score || 0) * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>

        {/* Grok */}
        <div className="p-3 sm:p-4 bg-gray-800/50 rounded-lg border border-blue-500/30">
          <div className="flex items-center gap-1.5 sm:gap-2 mb-2 sm:mb-3">
            <GrokIcon />
            <span className="font-medium text-white text-sm sm:text-base">Grok</span>
          </div>
          <div className="space-y-1.5 sm:space-y-2">
            <div>
              <span className="text-xs text-gray-400">Pick:</span>
              <div className="text-white font-medium text-sm sm:text-base truncate">
                {grok.recommended_bet === 'pass' ? 'Pass' : formatBetRecommendation(grok.recommended_bet || '')}
              </div>
            </div>
            <div>
              <span className="text-xs text-gray-400">Confidence:</span>
              <div className="text-white font-medium text-sm sm:text-base">
                {((grok.confidence_score || 0) * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Key Factors Comparison - collapsible on mobile */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
        <details className="sm:block" open>
          <summary className="sm:hidden text-sm font-medium text-orange-400 mb-2 flex items-center gap-1 cursor-pointer list-none">
            <ClaudeIcon /> <span>Claude Factors</span>
            <svg className="w-4 h-4 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <h4 className="hidden sm:flex text-sm font-medium text-orange-400 mb-2 items-center gap-1">
            <ClaudeIcon /> Key Factors
          </h4>
          <ul className="space-y-1 mt-2 sm:mt-0">
            {claude.key_factors?.slice(0, 3).map((factor, i) => (
              <li key={i} className="flex items-start gap-2 text-xs sm:text-sm">
                <span className="text-orange-400 mt-0.5">•</span>
                <span className="text-gray-300">{factor}</span>
              </li>
            ))}
          </ul>
        </details>
        <details className="sm:block" open>
          <summary className="sm:hidden text-sm font-medium text-blue-400 mb-2 flex items-center gap-1 cursor-pointer list-none">
            <GrokIcon /> <span>Grok Factors</span>
            <svg className="w-4 h-4 ml-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </summary>
          <h4 className="hidden sm:flex text-sm font-medium text-blue-400 mb-2 items-center gap-1">
            <GrokIcon /> Key Factors
          </h4>
          <ul className="space-y-1 mt-2 sm:mt-0">
            {grok.key_factors?.slice(0, 3).map((factor, i) => (
              <li key={i} className="flex items-start gap-2 text-xs sm:text-sm">
                <span className="text-blue-400 mt-0.5">•</span>
                <span className="text-gray-300">{factor}</span>
              </li>
            ))}
          </ul>
        </details>
      </div>
    </div>
  );
}

function AnalysisContent({ analysis }: { analysis: AIAnalysis }) {
  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Recommendation - responsive layout */}
      {analysis.recommended_bet && analysis.recommended_bet !== 'pass' && (
        <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="text-xl sm:text-2xl shrink-0">💰</div>
          <div className="flex-1 min-w-0">
            <div className="text-xs sm:text-sm text-green-400 font-medium">
              Recommended Bet
            </div>
            <div className="text-white font-semibold text-sm sm:text-base truncate">
              {formatBetRecommendation(analysis.recommended_bet)}
            </div>
          </div>
          {analysis.confidence_score && (
            <div className="text-right shrink-0">
              <div className="text-xl sm:text-2xl font-bold text-green-400">
                {(analysis.confidence_score * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-gray-400 hidden sm:block">confidence</div>
            </div>
          )}
        </div>
      )}

      {analysis.recommended_bet === 'pass' && (
        <div className="flex items-center gap-2 sm:gap-3 p-3 sm:p-4 bg-gray-500/10 border border-gray-500/30 rounded-lg">
          <div className="text-xl sm:text-2xl shrink-0">⏸️</div>
          <div>
            <div className="text-xs sm:text-sm text-gray-400 font-medium">
              Recommendation
            </div>
            <div className="text-white font-semibold text-sm sm:text-base">Pass on this game</div>
          </div>
        </div>
      )}

      {/* Key Factors */}
      {analysis.key_factors && analysis.key_factors.length > 0 && (
        <div>
          <h4 className="text-xs sm:text-sm font-medium text-gray-400 mb-2">
            Key Factors
          </h4>
          <ul className="space-y-1.5 sm:space-y-2">
            {analysis.key_factors.map((factor, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5 shrink-0">•</span>
                <span className="text-gray-300 text-sm">{factor}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Reasoning */}
      {analysis.reasoning && (
        <div>
          <h4 className="text-xs sm:text-sm font-medium text-gray-400 mb-2">Analysis</h4>
          <p className="text-gray-300 leading-relaxed text-sm">{analysis.reasoning}</p>
        </div>
      )}

      {/* Full Response (collapsed by default) */}
      {analysis.response && analysis.response !== analysis.reasoning && (
        <details className="group">
          <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-400 py-2 min-h-[44px] flex items-center">
            View full AI response
          </summary>
          <div className="mt-2 p-3 sm:p-4 bg-gray-800/50 rounded-lg overflow-x-auto">
            <pre className="text-xs sm:text-sm text-gray-400 whitespace-pre-wrap font-mono">
              {analysis.response}
            </pre>
          </div>
        </details>
      )}

      {/* Metadata - stack on mobile */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 text-xs text-gray-500 pt-3 sm:pt-4 border-t border-gray-800">
        <span>
          Generated:{' '}
          {new Date(analysis.created_at).toLocaleDateString()}
        </span>
        {analysis.tokens_used && <span>{analysis.tokens_used} tokens</span>}
      </div>
    </div>
  );
}

function formatBetRecommendation(bet: string): string {
  const parts = bet.split('_');
  if (parts.length < 2) return bet;

  const side = parts[0].charAt(0).toUpperCase() + parts[0].slice(1);
  const type = parts[1] === 'spread' ? 'Spread' : parts[1] === 'ml' ? 'Moneyline' : parts[1];

  return `${side} ${type}`;
}

// Simple SVG icons
function ClaudeIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="text-orange-400"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z" />
    </svg>
  );
}

function GrokIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="text-blue-400"
    >
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  );
}

function CompareIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="currentColor"
      className="text-purple-400"
    >
      <path d="M10 3H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1zM9 9H5V5h4v4zm11-6h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1V4a1 1 0 0 0-1-1zm-1 6h-4V5h4v4zm1 4h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1zm-1 6h-4v-4h4v4zm-9-6H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1v-6a1 1 0 0 0-1-1zm-1 6H5v-4h4v4z" />
    </svg>
  );
}

// Standalone analysis card for a single provider
interface SingleAnalysisProps {
  analysis: AIAnalysis | null;
  provider: AIProvider;
  onRequest?: () => Promise<void>;
  isLoading?: boolean;
}

export function SingleAnalysisCard({
  analysis,
  provider,
  onRequest,
  isLoading,
}: SingleAnalysisProps) {
  const providerName = provider === 'claude' ? 'Claude' : 'Grok';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <div className="flex items-center gap-2 mb-4">
        {provider === 'claude' ? <ClaudeIcon /> : <GrokIcon />}
        <h3 className="font-semibold text-white">{providerName} Analysis</h3>
      </div>

      {isLoading ? (
        // Content-aware skeleton loading
        <AIAnalysisSkeleton />
      ) : analysis ? (
        <AnalysisContent analysis={analysis} />
      ) : (
        <div className="text-center py-6">
          <p className="text-gray-400 mb-3">No analysis yet</p>
          {onRequest && (
            <button
              onClick={onRequest}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
            >
              Generate Analysis
            </button>
          )}
        </div>
      )}
    </div>
  );
}

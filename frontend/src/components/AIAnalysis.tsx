'use client';

import { useState } from 'react';
import type { AIAnalysis, AIProvider } from '@/lib/types';

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
  const [activeProvider, setActiveProvider] = useState<AIProvider>('claude');

  const claudeAnalysis = analyses.find((a) => a.ai_provider === 'claude');
  const grokAnalysis = analyses.find((a) => a.ai_provider === 'grok');

  const activeAnalysis =
    activeProvider === 'claude' ? claudeAnalysis : grokAnalysis;

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Tab Header */}
      <div className="flex border-b border-gray-800">
        <button
          onClick={() => setActiveProvider('claude')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeProvider === 'claude'
              ? 'bg-gray-800 text-white border-b-2 border-blue-500'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            <ClaudeIcon />
            Claude
            {claudeAnalysis && (
              <span className="text-xs text-green-400">Ready</span>
            )}
          </span>
        </button>
        <button
          onClick={() => setActiveProvider('grok')}
          className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
            activeProvider === 'grok'
              ? 'bg-gray-800 text-white border-b-2 border-blue-500'
              : 'text-gray-400 hover:text-white hover:bg-gray-800/50'
          }`}
        >
          <span className="flex items-center justify-center gap-2">
            <GrokIcon />
            Grok
            {grokAnalysis && (
              <span className="text-xs text-green-400">Ready</span>
            )}
          </span>
        </button>
      </div>

      {/* Content */}
      <div className="p-6">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
            <span className="ml-3 text-gray-400">Generating analysis...</span>
          </div>
        ) : activeAnalysis ? (
          <AnalysisContent analysis={activeAnalysis} />
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-400 mb-4">
              No {activeProvider === 'claude' ? 'Claude' : 'Grok'} analysis
              available yet.
            </p>
            {onRequestAnalysis && (
              <button
                onClick={() => onRequestAnalysis(activeProvider)}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                Generate {activeProvider === 'claude' ? 'Claude' : 'Grok'}{' '}
                Analysis
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function AnalysisContent({ analysis }: { analysis: AIAnalysis }) {
  return (
    <div className="space-y-6">
      {/* Recommendation */}
      {analysis.recommended_bet && analysis.recommended_bet !== 'pass' && (
        <div className="flex items-center gap-3 p-4 bg-green-500/10 border border-green-500/30 rounded-lg">
          <div className="text-2xl">💰</div>
          <div>
            <div className="text-sm text-green-400 font-medium">
              Recommended Bet
            </div>
            <div className="text-white font-semibold">
              {formatBetRecommendation(analysis.recommended_bet)}
            </div>
          </div>
          {analysis.confidence_score && (
            <div className="ml-auto text-right">
              <div className="text-2xl font-bold text-green-400">
                {(analysis.confidence_score * 100).toFixed(0)}%
              </div>
              <div className="text-xs text-gray-400">confidence</div>
            </div>
          )}
        </div>
      )}

      {analysis.recommended_bet === 'pass' && (
        <div className="flex items-center gap-3 p-4 bg-gray-500/10 border border-gray-500/30 rounded-lg">
          <div className="text-2xl">⏸️</div>
          <div>
            <div className="text-sm text-gray-400 font-medium">
              Recommendation
            </div>
            <div className="text-white font-semibold">Pass on this game</div>
          </div>
        </div>
      )}

      {/* Key Factors */}
      {analysis.key_factors && analysis.key_factors.length > 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">
            Key Factors
          </h4>
          <ul className="space-y-2">
            {analysis.key_factors.map((factor, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-blue-400 mt-0.5">•</span>
                <span className="text-gray-300">{factor}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Reasoning */}
      {analysis.reasoning && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2">Analysis</h4>
          <p className="text-gray-300 leading-relaxed">{analysis.reasoning}</p>
        </div>
      )}

      {/* Full Response (collapsed by default) */}
      {analysis.response && analysis.response !== analysis.reasoning && (
        <details className="group">
          <summary className="text-sm text-gray-500 cursor-pointer hover:text-gray-400">
            View full AI response
          </summary>
          <div className="mt-3 p-4 bg-gray-800/50 rounded-lg">
            <pre className="text-sm text-gray-400 whitespace-pre-wrap font-mono">
              {analysis.response}
            </pre>
          </div>
        </details>
      )}

      {/* Metadata */}
      <div className="flex items-center justify-between text-xs text-gray-500 pt-4 border-t border-gray-800">
        <span>
          Generated:{' '}
          {new Date(analysis.created_at).toLocaleString()}
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
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-500"></div>
        </div>
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

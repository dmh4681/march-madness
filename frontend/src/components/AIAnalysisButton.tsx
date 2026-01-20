'use client';

import { useState } from 'react';
import type { AIProvider } from '@/lib/types';

interface AIAnalysisButtonProps {
  gameId: string;
  hasClaudeAnalysis?: boolean;
  hasGrokAnalysis?: boolean;
  apiUrl?: string;
}

export function AIAnalysisButton({
  gameId,
  hasClaudeAnalysis = false,
  hasGrokAnalysis = false,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-e5efb.up.railway.app',
}: AIAnalysisButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<AIProvider>('claude');

  const runAnalysis = async (provider: AIProvider = selectedProvider) => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout

      const requestUrl = `${apiUrl}/ai-analysis`;
      const requestBody = JSON.stringify({
        game_id: gameId,
        provider: provider,
      });

      console.log('Making request to:', requestUrl);
      console.log('Request body:', requestBody);

      const response = await fetch(requestUrl, {
        method: 'POST',
        mode: 'cors',
        cache: 'no-cache',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
        body: requestBody,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      // Read response text first to handle empty responses
      const text = await response.text();

      // Log for debugging
      console.log('AI Analysis Response:', {
        status: response.status,
        statusText: response.statusText,
        textLength: text?.length || 0,
        textPreview: text?.substring(0, 200),
      });

      if (!response.ok) {
        let errorMessage = `Failed (${response.status}): `;
        if (text) {
          try {
            const data = JSON.parse(text);
            errorMessage += data.detail || text.substring(0, 100);
          } catch {
            errorMessage += text.substring(0, 100) || 'Unknown error';
          }
        } else {
          errorMessage += 'Empty response';
        }
        throw new Error(errorMessage);
      }

      // Verify we got valid JSON back
      if (!text) {
        throw new Error('Empty response from server');
      }

      try {
        JSON.parse(text); // Validate JSON
      } catch {
        throw new Error('Invalid response format');
      }

      setSuccess(true);
      // Refresh the page to show new analysis
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        setError('Request timed out. The analysis is taking too long.');
      } else {
        setError(err instanceof Error ? err.message : 'Unknown error');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRunAnalysis = () => {
    runAnalysis(selectedProvider);
  };

  const providerLabel = selectedProvider === 'claude' ? 'Claude' : 'Grok';
  const hasCurrentProviderAnalysis = selectedProvider === 'claude' ? hasClaudeAnalysis : hasGrokAnalysis;

  if (success) {
    return (
      <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
        <p className="text-green-400 font-medium">Analysis complete! Refreshing...</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Provider Toggle */}
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        <button
          type="button"
          onClick={() => setSelectedProvider('claude')}
          disabled={loading}
          className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
            selectedProvider === 'claude'
              ? 'bg-orange-500/20 text-orange-400 border-r border-gray-700'
              : 'bg-gray-800 text-gray-400 hover:text-white border-r border-gray-700'
          }`}
        >
          <span className="flex items-center justify-center gap-1.5">
            <ClaudeIcon />
            Claude
            {hasClaudeAnalysis && <span className="text-xs text-green-400">*</span>}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setSelectedProvider('grok')}
          disabled={loading}
          className={`flex-1 px-3 py-2 text-sm font-medium transition-colors ${
            selectedProvider === 'grok'
              ? 'bg-blue-500/20 text-blue-400'
              : 'bg-gray-800 text-gray-400 hover:text-white'
          }`}
        >
          <span className="flex items-center justify-center gap-1.5">
            <GrokIcon />
            Grok
            {hasGrokAnalysis && <span className="text-xs text-green-400">*</span>}
          </span>
        </button>
      </div>

      {/* Run Button */}
      <button
        onClick={handleRunAnalysis}
        disabled={loading}
        className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
          loading
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : selectedProvider === 'claude'
            ? 'bg-orange-600 hover:bg-orange-700 text-white'
            : 'bg-blue-600 hover:bg-blue-700 text-white'
        }`}
      >
        {loading ? (
          <span className="flex items-center justify-center gap-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            Running {providerLabel} Analysis...
          </span>
        ) : hasCurrentProviderAnalysis ? (
          `Re-run ${providerLabel} Analysis`
        ) : (
          `Run ${providerLabel} Analysis`
        )}
      </button>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      <p className="text-xs text-gray-500 text-center">
        {hasClaudeAnalysis || hasGrokAnalysis ? '* = analysis exists' : `Powered by ${providerLabel}`}
      </p>
    </div>
  );
}

// Simple SVG icons
function ClaudeIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z" />
    </svg>
  );
}

function GrokIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="currentColor"
    >
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  );
}

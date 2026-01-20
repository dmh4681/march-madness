'use client';

import { useState } from 'react';

interface AIAnalysisButtonProps {
  gameId: string;
  hasExistingAnalysis: boolean;
  apiUrl?: string;
}

export function AIAnalysisButton({
  gameId,
  hasExistingAnalysis,
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-e5efb.up.railway.app',
}: AIAnalysisButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 120000); // 2 minute timeout

      const response = await fetch(`${apiUrl}/ai-analysis`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          game_id: gameId,
          provider: 'claude',
        }),
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

  if (success) {
    return (
      <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
        <p className="text-green-400 font-medium">Analysis complete! Refreshing...</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <button
        onClick={runAnalysis}
        disabled={loading}
        className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
          loading
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
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
            Running Claude Analysis...
          </span>
        ) : hasExistingAnalysis ? (
          'Re-run AI Analysis'
        ) : (
          'Run AI Analysis'
        )}
      </button>

      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      <p className="text-xs text-gray-500 text-center">
        Powered by Claude AI
      </p>
    </div>
  );
}

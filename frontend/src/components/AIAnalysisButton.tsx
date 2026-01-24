'use client';

import { useState, useCallback } from 'react';
import type { AIProvider } from '@/lib/types';

// Error types for user-friendly messages
type ErrorType = 'timeout' | 'network' | 'server' | 'api_limit' | 'unknown';

interface ErrorState {
  type: ErrorType;
  message: string;
  canRetry: boolean;
}

// Parse error response and categorize it
function parseError(err: unknown, response?: Response, responseText?: string): ErrorState {
  // Handle abort/timeout errors
  if (err instanceof Error && err.name === 'AbortError') {
    return {
      type: 'timeout',
      message: 'The AI analysis is taking longer than expected. This can happen during high traffic or for complex games.',
      canRetry: true,
    };
  }

  // Handle network errors (fetch failed)
  if (err instanceof TypeError && err.message.includes('fetch')) {
    return {
      type: 'network',
      message: 'Unable to connect to the server. Please check your internet connection.',
      canRetry: true,
    };
  }

  // Handle HTTP status codes
  if (response) {
    const status = response.status;

    // Rate limiting
    if (status === 429) {
      return {
        type: 'api_limit',
        message: 'Too many requests. Please wait a moment before trying again.',
        canRetry: true,
      };
    }

    // Server errors (5xx)
    if (status >= 500) {
      // Check for specific Claude API errors in response
      if (responseText?.includes('overloaded') || responseText?.includes('capacity')) {
        return {
          type: 'api_limit',
          message: 'The AI service is currently experiencing high demand. Please try again shortly.',
          canRetry: true,
        };
      }
      return {
        type: 'server',
        message: 'The server encountered an error. Our team has been notified.',
        canRetry: true,
      };
    }

    // Client errors (4xx)
    if (status >= 400) {
      let detail = '';
      if (responseText) {
        try {
          const data = JSON.parse(responseText);
          detail = data.detail || '';
        } catch {
          detail = responseText.substring(0, 100);
        }
      }
      return {
        type: 'unknown',
        message: detail || `Request failed (${status})`,
        canRetry: status !== 400, // Don't retry bad requests
      };
    }
  }

  // Generic error
  return {
    type: 'unknown',
    message: err instanceof Error ? err.message : 'An unexpected error occurred',
    canRetry: true,
  };
}

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
  apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
}: AIAnalysisButtonProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<ErrorState | null>(null);
  const [success, setSuccess] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<AIProvider>('claude');
  const [retryCount, setRetryCount] = useState(0);

  const runAnalysis = useCallback(async (provider: AIProvider = selectedProvider, isRetry = false) => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    if (isRetry) {
      setRetryCount(prev => prev + 1);
    } else {
      setRetryCount(0);
    }

    let response: Response | undefined;
    let responseText: string | undefined;

    try {
      const controller = new AbortController();
      // Longer timeout for retries (up to 3 minutes)
      const timeout = isRetry ? 180000 : 120000;
      const timeoutId = setTimeout(() => controller.abort(), timeout);

      const requestUrl = `${apiUrl}/ai-analysis`;
      const requestBody = JSON.stringify({
        game_id: gameId,
        provider: provider,
      });

      console.log('Making request to:', requestUrl);
      console.log('Request body:', requestBody);

      response = await fetch(requestUrl, {
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
      responseText = await response.text();

      // Log for debugging
      console.log('AI Analysis Response:', {
        status: response.status,
        statusText: response.statusText,
        textLength: responseText?.length || 0,
        textPreview: responseText?.substring(0, 200),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      // Verify we got valid JSON back
      if (!responseText) {
        throw new Error('Empty response from server');
      }

      try {
        JSON.parse(responseText); // Validate JSON
      } catch {
        throw new Error('Invalid response format');
      }

      setSuccess(true);
      // Refresh the page to show new analysis
      setTimeout(() => {
        window.location.reload();
      }, 1500);
    } catch (err) {
      const errorState = parseError(err, response, responseText);
      setError(errorState);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, gameId, selectedProvider]);

  const handleRunAnalysis = () => {
    runAnalysis(selectedProvider);
  };

  const handleRetry = () => {
    runAnalysis(selectedProvider, true);
  };

  const providerLabel = selectedProvider === 'claude' ? 'Claude' : 'Grok';
  const hasCurrentProviderAnalysis = selectedProvider === 'claude' ? hasClaudeAnalysis : hasGrokAnalysis;

  if (success) {
    return (
      <div className="p-4 bg-green-500/10 border border-green-500/30 rounded-lg text-center">
        <div className="flex items-center justify-center gap-2">
          <svg className="h-5 w-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <p className="text-green-400 font-medium">Analysis complete! Refreshing...</p>
        </div>
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

      {/* Loading progress hint */}
      {loading && (
        <p className="text-xs text-gray-500 text-center">
          AI analysis typically completes within 30-60 seconds
        </p>
      )}

      {/* Error State with Retry */}
      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <div className="flex items-start gap-3">
            <ErrorIcon type={error.type} />
            <div className="flex-1">
              <p className="text-red-400 text-sm font-medium mb-1">
                {getErrorTitle(error.type)}
              </p>
              <p className="text-gray-400 text-sm">{error.message}</p>
              {error.canRetry && retryCount < 3 && (
                <button
                  onClick={handleRetry}
                  className="mt-3 px-3 py-1.5 text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-md transition-colors inline-flex items-center gap-2"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Try Again {retryCount > 0 && `(${retryCount}/3)`}
                </button>
              )}
              {retryCount >= 3 && (
                <p className="mt-2 text-xs text-gray-500">
                  Multiple retries failed. Please try again later or contact support.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <p className="text-xs text-gray-500 text-center">
        {hasClaudeAnalysis || hasGrokAnalysis ? '* = analysis exists' : `Powered by ${providerLabel}`}
      </p>
    </div>
  );
}

// Get error title based on error type
function getErrorTitle(type: ErrorType): string {
  switch (type) {
    case 'timeout':
      return 'Request Timed Out';
    case 'network':
      return 'Connection Error';
    case 'server':
      return 'Server Error';
    case 'api_limit':
      return 'Service Busy';
    default:
      return 'Analysis Failed';
  }
}

// Error icon based on error type
function ErrorIcon({ type }: { type: ErrorType }) {
  const iconClass = "h-5 w-5 text-red-400 flex-shrink-0 mt-0.5";

  switch (type) {
    case 'timeout':
      return (
        <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'network':
      return (
        <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.111 16.404a5.5 5.5 0 017.778 0M12 20h.01m-7.08-7.071c3.904-3.905 10.236-3.905 14.14 0M1.394 9.393c5.857-5.857 15.355-5.857 21.213 0" />
        </svg>
      );
    case 'api_limit':
      return (
        <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      );
    default:
      return (
        <svg className={iconClass} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
      );
  }
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

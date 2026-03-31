'use client';

import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import type { ReactNode } from 'react';

export function BracketErrorBoundary({ children }: { children: ReactNode }) {
  return (
    <ErrorBoundary
      fallbackRender={({ retry }) => (
        <div className="text-center py-12 sm:py-16">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-500/10 mb-4">
            <svg
              className="w-7 h-7 text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-white mb-2">
            Bracket failed to render
          </h3>
          <p className="text-gray-400 mb-6 max-w-md mx-auto">
            There was an error displaying the bracket data. The data may be temporarily unavailable.
          </p>
          <div className="flex items-center justify-center gap-3">
            <button
              onClick={retry}
              className="px-5 py-2.5 bg-orange-600 hover:bg-orange-500 text-white rounded-lg transition-colors font-medium"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-5 py-2.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-white rounded-lg transition-colors font-medium"
            >
              Reload Page
            </button>
          </div>
        </div>
      )}
    >
      {children}
    </ErrorBoundary>
  );
}

'use client';

import dynamic from 'next/dynamic';
import { AIAnalysisSkeleton, AICompareViewSkeleton } from './ui/skeleton';

// Lazy loading skeleton for the entire AI Analysis Panel
function AIAnalysisPanelSkeleton() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      {/* Tab Header skeleton */}
      <div className="flex border-b border-gray-800">
        <div className="flex-1 px-3 sm:px-4 py-3 sm:py-3 min-h-[48px] bg-gray-800">
          <div className="flex items-center justify-center gap-1.5 sm:gap-2">
            <div className="w-4 h-4 bg-gray-700 rounded animate-pulse" />
            <div className="w-12 h-4 bg-gray-700 rounded animate-pulse hidden sm:block" />
          </div>
        </div>
        <div className="flex-1 px-3 sm:px-4 py-3 sm:py-3 min-h-[48px]">
          <div className="flex items-center justify-center gap-1.5 sm:gap-2">
            <div className="w-4 h-4 bg-gray-700 rounded animate-pulse" />
            <div className="w-10 h-4 bg-gray-700 rounded animate-pulse hidden sm:block" />
          </div>
        </div>
      </div>
      {/* Content skeleton */}
      <div className="p-4 sm:p-6">
        <AIAnalysisSkeleton />
      </div>
    </div>
  );
}

// Lazy loading skeleton for the AI Analysis Button
function AIAnalysisButtonSkeleton() {
  return (
    <div className="space-y-3">
      {/* Provider Toggle skeleton */}
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        <div className="flex-1 px-3 py-2 bg-gray-800">
          <div className="flex items-center justify-center gap-1.5">
            <div className="w-3.5 h-3.5 bg-gray-700 rounded animate-pulse" />
            <div className="w-12 h-4 bg-gray-700 rounded animate-pulse" />
          </div>
        </div>
        <div className="flex-1 px-3 py-2 bg-gray-800 border-l border-gray-700">
          <div className="flex items-center justify-center gap-1.5">
            <div className="w-3.5 h-3.5 bg-gray-700 rounded animate-pulse" />
            <div className="w-10 h-4 bg-gray-700 rounded animate-pulse" />
          </div>
        </div>
      </div>
      {/* Button skeleton */}
      <div className="w-full py-3 px-4 rounded-lg bg-gray-700 animate-pulse">
        <div className="h-5 w-32 mx-auto bg-gray-600 rounded" />
      </div>
      {/* Footer text skeleton */}
      <div className="h-3 w-24 mx-auto bg-gray-800 rounded animate-pulse" />
    </div>
  );
}

// Lazy load AIAnalysisPanel with Suspense fallback
export const LazyAIAnalysisPanel = dynamic(
  () => import('./AIAnalysis').then((mod) => ({ default: mod.AIAnalysisPanel })),
  {
    loading: () => <AIAnalysisPanelSkeleton />,
    ssr: true, // Keep SSR enabled for SEO
  }
);

// Lazy load AIAnalysisButton with Suspense fallback
export const LazyAIAnalysisButton = dynamic(
  () => import('./AIAnalysisButton').then((mod) => ({ default: mod.AIAnalysisButton })),
  {
    loading: () => <AIAnalysisButtonSkeleton />,
    ssr: true,
  }
);

// Re-export skeleton components for direct use if needed
export { AIAnalysisPanelSkeleton, AIAnalysisButtonSkeleton };

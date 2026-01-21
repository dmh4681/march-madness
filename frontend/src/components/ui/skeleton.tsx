'use client';

import { cn } from '@/lib/utils';

interface SkeletonProps {
  className?: string;
}

// Base skeleton with shimmer animation overlay
export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'relative overflow-hidden bg-gray-800 rounded',
        className
      )}
    >
      {/* Shimmer overlay */}
      <div className="absolute inset-0 animate-shimmer" />
    </div>
  );
}

// Skeleton for GameCard component - responsive padding matches GameCard
export function GameCardSkeleton() {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-3 sm:p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-4 w-16" />
        <div className="flex items-center gap-2">
          <Skeleton className="h-7 sm:h-5 w-14 sm:w-12 rounded" />
        </div>
      </div>

      {/* Teams - touch-friendly spacing on mobile */}
      <div className="space-y-3 sm:space-y-2 mb-4">
        {/* Away Team */}
        <div className="flex items-center justify-between min-h-[44px] sm:min-h-0">
          <Skeleton className="h-5 w-32" />
          <div className="flex items-center gap-2 sm:gap-3">
            <Skeleton className="h-4 w-10" />
            <Skeleton className="h-4 w-14 hidden sm:block" />
          </div>
        </div>

        {/* Home Team */}
        <div className="flex items-center justify-between min-h-[44px] sm:min-h-0">
          <Skeleton className="h-5 w-36" />
          <div className="flex items-center gap-2 sm:gap-3">
            <Skeleton className="h-4 w-10" />
            <Skeleton className="h-4 w-14 hidden sm:block" />
          </div>
        </div>
      </div>

      {/* Total - hidden on mobile like GameCard */}
      <div className="hidden sm:flex items-center justify-between mb-3 pb-3 border-b border-gray-800">
        <Skeleton className="h-4 w-10" />
        <Skeleton className="h-4 w-16" />
      </div>

      {/* Prediction - touch-friendly */}
      <div className="flex items-center justify-between min-h-[44px] sm:min-h-0">
        <div className="flex items-center gap-2">
          <Skeleton className="h-[44px] sm:h-6 w-20 sm:w-16 rounded-full" />
          <Skeleton className="h-4 w-24 hidden sm:block" />
        </div>
        <Skeleton className="h-4 w-20" />
      </div>
    </div>
  );
}

// Skeleton for AI Analysis content
export function AIAnalysisSkeleton() {
  return (
    <div className="space-y-6">
      {/* Recommendation box */}
      <div className="flex items-center gap-3 p-4 bg-gray-800/50 border border-gray-700 rounded-lg">
        <Skeleton className="h-8 w-8 rounded" />
        <div className="flex-1">
          <Skeleton className="h-3 w-24 mb-2" />
          <Skeleton className="h-5 w-40" />
        </div>
        <div className="text-right">
          <Skeleton className="h-8 w-16 mb-1" />
          <Skeleton className="h-3 w-12" />
        </div>
      </div>

      {/* Key factors */}
      <div>
        <Skeleton className="h-4 w-20 mb-3" />
        <div className="space-y-2">
          <div className="flex items-start gap-2">
            <Skeleton className="h-2 w-2 rounded-full mt-1.5" />
            <Skeleton className="h-4 w-full max-w-md" />
          </div>
          <div className="flex items-start gap-2">
            <Skeleton className="h-2 w-2 rounded-full mt-1.5" />
            <Skeleton className="h-4 w-full max-w-sm" />
          </div>
          <div className="flex items-start gap-2">
            <Skeleton className="h-2 w-2 rounded-full mt-1.5" />
            <Skeleton className="h-4 w-full max-w-lg" />
          </div>
        </div>
      </div>

      {/* Analysis text */}
      <div>
        <Skeleton className="h-4 w-16 mb-3" />
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      </div>

      {/* Metadata */}
      <div className="flex items-center justify-between pt-4 border-t border-gray-800">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}

// Skeleton for compare view
export function AICompareViewSkeleton() {
  return (
    <div className="space-y-6">
      {/* Consensus Banner */}
      <div className="p-4 rounded-lg border border-gray-700 bg-gray-800/50">
        <div className="flex items-center gap-3">
          <Skeleton className="h-8 w-8" />
          <div>
            <Skeleton className="h-3 w-20 mb-2" />
            <Skeleton className="h-5 w-48" />
          </div>
          <div className="ml-auto text-right">
            <Skeleton className="h-8 w-12 mb-1" />
            <Skeleton className="h-3 w-16" />
          </div>
        </div>
      </div>

      {/* Side by side cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-4 w-14" />
          </div>
          <div className="space-y-2">
            <div>
              <Skeleton className="h-3 w-8 mb-1" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div>
              <Skeleton className="h-3 w-16 mb-1" />
              <Skeleton className="h-4 w-12" />
            </div>
          </div>
        </div>
        <div className="p-4 bg-gray-800/50 rounded-lg border border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-4 w-10" />
          </div>
          <div className="space-y-2">
            <div>
              <Skeleton className="h-3 w-8 mb-1" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div>
              <Skeleton className="h-3 w-16 mb-1" />
              <Skeleton className="h-4 w-12" />
            </div>
          </div>
        </div>
      </div>

      {/* Key factors comparison */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Skeleton className="h-4 w-20 mb-2" />
          <div className="space-y-1">
            <Skeleton className="h-3 w-full max-w-xs" />
            <Skeleton className="h-3 w-full max-w-[200px]" />
            <Skeleton className="h-3 w-full max-w-[220px]" />
          </div>
        </div>
        <div>
          <Skeleton className="h-4 w-20 mb-2" />
          <div className="space-y-1">
            <Skeleton className="h-3 w-full max-w-xs" />
            <Skeleton className="h-3 w-full max-w-[180px]" />
            <Skeleton className="h-3 w-full max-w-[240px]" />
          </div>
        </div>
      </div>
    </div>
  );
}


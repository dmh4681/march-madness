import { RegionCardSkeleton, RegionSeedSidebarSkeleton } from '@/components/ui/skeleton';

export default function MarchMadnessLoading() {
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header skeleton */}
      <header className="border-b border-gray-800 bg-gray-900/50">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:py-4">
          <div className="h-7 w-48 bg-gray-800 rounded animate-pulse" />
          <div className="h-4 w-32 bg-gray-800 rounded animate-pulse mt-1" />
        </div>
      </header>

      {/* Hero skeleton */}
      <div className="bg-gradient-to-b from-orange-900/20 to-black border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-3 sm:px-4 py-6 sm:py-12">
          <div className="flex items-center gap-3 mb-2">
            <div className="h-8 sm:h-10 w-64 bg-gray-800 rounded animate-pulse" />
            <div className="h-6 w-24 bg-gray-800 rounded animate-pulse" />
          </div>
          <div className="h-5 w-48 bg-gray-800 rounded animate-pulse mb-4 sm:mb-6" />
          <div className="flex gap-2 sm:gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-10 w-28 bg-gray-800/50 rounded-lg animate-pulse" />
            ))}
          </div>
        </div>
      </div>

      {/* Content skeleton */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        {/* Region filter tabs skeleton */}
        <div className="flex gap-2 mb-4">
          {['All', 'East', 'West', 'South', 'Midwest'].map((r) => (
            <div key={r} className="h-11 w-20 bg-gray-800 rounded-lg animate-pulse" />
          ))}
        </div>

        {/* Main grid: sidebar + region cards */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
          {/* Seed sidebar skeleton - desktop only */}
          <div className="hidden lg:block lg:col-span-1">
            <RegionSeedSidebarSkeleton />
          </div>

          {/* Region cards skeleton */}
          <div className="lg:col-span-2 grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <RegionCardSkeleton key={i} matchupCount={4} />
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

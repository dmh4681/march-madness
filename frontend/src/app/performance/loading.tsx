export default function PerformanceLoading() {
  return (
    <div className="min-h-screen bg-black text-white">
      {/* Header skeleton */}
      <header className="border-b border-gray-800 bg-gray-900/50 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-3 sm:py-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="h-7 w-48 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-32 bg-gray-800 rounded animate-pulse mt-1" />
            </div>
            <div className="hidden sm:flex items-center gap-6">
              <div className="h-4 w-20 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-28 bg-gray-800 rounded animate-pulse" />
              <div className="h-4 w-24 bg-gray-800 rounded animate-pulse" />
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8">
        {/* Page title skeleton */}
        <div className="mb-4 sm:mb-8">
          <div className="h-8 w-56 bg-gray-800 rounded animate-pulse mb-2" />
          <div className="h-4 w-80 bg-gray-800 rounded animate-pulse" />
        </div>

        {/* Season stats cards skeleton */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-gray-900 border border-gray-800 rounded-xl p-4 animate-pulse">
              <div className="h-4 w-20 bg-gray-800 rounded mb-2" />
              <div className="h-8 w-16 bg-gray-800 rounded" />
            </div>
          ))}
        </div>

        {/* Confidence tier breakdown skeleton */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 sm:p-6 mb-6">
          <div className="h-5 w-44 bg-gray-800 rounded animate-pulse mb-4" />
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-gray-800/50 rounded-lg p-4 animate-pulse">
                <div className="h-5 w-20 bg-gray-800 rounded mb-3" />
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <div className="h-4 w-16 bg-gray-800 rounded" />
                    <div className="h-4 w-12 bg-gray-800 rounded" />
                  </div>
                  <div className="flex justify-between">
                    <div className="h-4 w-16 bg-gray-800 rounded" />
                    <div className="h-4 w-12 bg-gray-800 rounded" />
                  </div>
                  <div className="flex justify-between">
                    <div className="h-4 w-16 bg-gray-800 rounded" />
                    <div className="h-4 w-12 bg-gray-800 rounded" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent picks skeleton */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 sm:p-6">
          <div className="h-5 w-28 bg-gray-800 rounded animate-pulse mb-4" />
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800 animate-pulse">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-24 bg-gray-800 rounded" />
                  <div className="h-4 w-4 bg-gray-800 rounded" />
                  <div className="h-5 w-24 bg-gray-800 rounded" />
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-5 w-16 bg-gray-800 rounded-full" />
                  <div className="h-5 w-10 bg-gray-800 rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}

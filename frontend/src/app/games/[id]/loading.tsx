export default function GameDetailLoading() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Game Header Skeleton */}
        <div className="bg-gray-900 rounded-xl p-6 mb-6 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="h-8 w-32 bg-gray-800 rounded" />
              <div className="h-6 w-8 bg-gray-800 rounded" />
              <div className="h-8 w-32 bg-gray-800 rounded" />
            </div>
            <div className="h-6 w-24 bg-gray-800 rounded" />
          </div>
          <div className="mt-4 flex gap-4">
            <div className="h-4 w-40 bg-gray-800 rounded" />
            <div className="h-4 w-32 bg-gray-800 rounded" />
          </div>
        </div>

        {/* Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - Stats */}
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-gray-900 rounded-xl p-4 animate-pulse">
                <div className="h-5 w-24 bg-gray-800 rounded mb-4" />
                <div className="space-y-3">
                  {[1, 2, 3, 4].map((j) => (
                    <div key={j} className="flex justify-between">
                      <div className="h-4 w-20 bg-gray-800 rounded" />
                      <div className="h-4 w-16 bg-gray-800 rounded" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Right Column - AI Analysis */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-gray-900 rounded-xl p-6 animate-pulse">
              <div className="h-6 w-32 bg-gray-800 rounded mb-4" />
              <div className="flex gap-2 mb-6">
                <div className="h-10 w-24 bg-gray-800 rounded-lg" />
                <div className="h-10 w-24 bg-gray-800 rounded-lg" />
                <div className="h-10 w-24 bg-gray-800 rounded-lg" />
              </div>
              <div className="space-y-4">
                <div className="h-20 bg-gray-800 rounded-lg" />
                <div className="h-4 w-3/4 bg-gray-800 rounded" />
                <div className="h-4 w-1/2 bg-gray-800 rounded" />
                <div className="h-32 bg-gray-800 rounded-lg" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

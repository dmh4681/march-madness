export default function DashboardLoading() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="h-8 w-64 bg-gray-800 rounded mb-2 animate-pulse" />
        <div className="h-4 w-48 bg-gray-800 rounded mb-8 animate-pulse" />

        {/* Stats Row */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="bg-gray-900 rounded-xl p-4 animate-pulse">
              <div className="h-4 w-20 bg-gray-800 rounded mb-2" />
              <div className="h-8 w-16 bg-gray-800 rounded" />
            </div>
          ))}
        </div>

        {/* Games Table Skeleton */}
        <div className="bg-gray-900 rounded-xl p-4 animate-pulse">
          <div className="h-6 w-40 bg-gray-800 rounded mb-4" />
          <div className="space-y-3">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="flex items-center justify-between py-2 border-b border-gray-800">
                <div className="flex items-center gap-3">
                  <div className="h-5 w-28 bg-gray-800 rounded" />
                  <div className="h-4 w-8 bg-gray-800 rounded" />
                  <div className="h-5 w-28 bg-gray-800 rounded" />
                </div>
                <div className="flex items-center gap-4">
                  <div className="h-5 w-16 bg-gray-800 rounded" />
                  <div className="h-5 w-20 bg-gray-800 rounded-full" />
                  <div className="h-5 w-12 bg-gray-800 rounded" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function GamesListLoading() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <div className="h-8 w-48 bg-gray-800 rounded mb-6 animate-pulse" />
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="bg-gray-900 rounded-xl p-4 animate-pulse">
              <div className="flex justify-between items-center mb-3">
                <div className="h-5 w-24 bg-gray-800 rounded" />
                <div className="h-5 w-16 bg-gray-800 rounded" />
              </div>
              <div className="flex items-center justify-between mb-2">
                <div className="h-6 w-28 bg-gray-800 rounded" />
                <div className="h-6 w-8 bg-gray-800 rounded" />
                <div className="h-6 w-28 bg-gray-800 rounded" />
              </div>
              <div className="flex gap-2 mt-3">
                <div className="h-6 w-16 bg-gray-800 rounded-full" />
                <div className="h-6 w-20 bg-gray-800 rounded-full" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function DashboardLoading() {
  return (
    <div className="h-screen flex flex-col bg-surface-50">
      {/* Top bar skeleton */}
      <header className="h-14 bg-white border-b border-surface-200 flex items-center px-4 gap-4">
        <div className="w-7 h-7 rounded-lg bg-surface-200 animate-pulse" />
        <div className="w-32 h-4 rounded bg-surface-200 animate-pulse" />
        <div className="flex-1" />
        <div className="w-20 h-3 rounded bg-surface-100 animate-pulse" />
      </header>

      <div className="flex-1 flex">
        {/* Sidebar skeleton */}
        <aside className="w-72 border-r border-surface-200 bg-white p-3 space-y-2">
          <div className="flex gap-1 mb-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="w-14 h-5 rounded-full bg-surface-100 animate-pulse" />
            ))}
          </div>
          {Array.from({ length: 12 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-3 py-2.5">
              <div className="w-2 h-2 rounded-full bg-surface-200 animate-pulse" />
              <div className="flex-1 space-y-1">
                <div className="w-24 h-3 rounded bg-surface-200 animate-pulse" />
                <div className="w-16 h-2 rounded bg-surface-100 animate-pulse" />
              </div>
            </div>
          ))}
        </aside>

        {/* Main content skeleton */}
        <main className="flex-1 flex flex-col">
          <div className="h-12 bg-white border-b border-surface-200 flex items-center px-5 gap-3">
            <div className="w-2.5 h-2.5 rounded-full bg-surface-200 animate-pulse" />
            <div className="w-28 h-4 rounded bg-surface-200 animate-pulse" />
          </div>
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="text-4xl mb-4 opacity-10 animate-pulse">&#9881;</div>
              <div className="w-48 h-3 rounded bg-surface-100 animate-pulse mx-auto" />
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

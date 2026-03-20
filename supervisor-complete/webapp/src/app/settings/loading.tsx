export default function SettingsLoading() {
  return (
    <div className="min-h-screen bg-surface-50 p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="w-32 h-6 rounded bg-surface-200 animate-pulse" />
        <div className="w-64 h-3 rounded bg-surface-100 animate-pulse" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="bg-white rounded-xl border border-surface-200 p-6 space-y-4">
            <div className="w-40 h-4 rounded bg-surface-200 animate-pulse" />
            <div className="space-y-3">
              <div className="h-10 rounded-lg bg-surface-100 animate-pulse" />
              <div className="h-10 rounded-lg bg-surface-100 animate-pulse" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

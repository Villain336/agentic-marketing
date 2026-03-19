export default function OnboardingLoading() {
  return (
    <div className="min-h-screen bg-white flex flex-col">
      <div className="h-1 bg-surface-100">
        <div className="h-full w-1/6 bg-brand-500 animate-pulse" />
      </div>
      <div className="flex-1 flex items-center justify-center">
        <div className="w-full max-w-2xl mx-auto p-8 space-y-6">
          <div className="w-48 h-6 rounded bg-surface-200 animate-pulse mx-auto" />
          <div className="w-72 h-3 rounded bg-surface-100 animate-pulse mx-auto" />
          <div className="space-y-4 mt-8">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-12 rounded-lg bg-surface-100 animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

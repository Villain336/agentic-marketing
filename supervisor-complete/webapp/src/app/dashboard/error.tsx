"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Dashboard error:", error);
  }, [error]);

  return (
    <div className="h-screen flex items-center justify-center bg-surface-50">
      <div className="max-w-md text-center p-8">
        <div className="text-4xl mb-4 opacity-30">&#9881;</div>
        <h2 className="text-lg font-semibold text-surface-900 mb-2">Dashboard Error</h2>
        <p className="text-sm text-surface-500 mb-4">
          {error.message || "Failed to load dashboard. The backend may be offline."}
        </p>
        <div className="flex gap-3 justify-center">
          <button onClick={reset} className="btn-primary text-sm px-5 py-2">
            Retry
          </button>
          <a href="/" className="btn-secondary text-sm px-5 py-2 inline-block">
            Home
          </a>
        </div>
      </div>
    </div>
  );
}

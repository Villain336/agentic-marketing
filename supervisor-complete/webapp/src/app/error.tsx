"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-surface-50">
      <div className="max-w-md text-center p-8">
        <div className="text-4xl mb-4 opacity-30">&#9888;</div>
        <h2 className="text-lg font-semibold text-surface-900 mb-2">Something went wrong</h2>
        <p className="text-sm text-surface-500 mb-6">
          {error.message || "An unexpected error occurred. Please try again."}
        </p>
        <button
          onClick={reset}
          className="btn-primary text-sm px-6 py-2"
        >
          Try again
        </button>
      </div>
    </div>
  );
}

"use client";

import { useEffect } from "react";

export default function OnboardingError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Onboarding error:", error);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-white">
      <div className="max-w-md text-center p-8">
        <div className="text-4xl mb-4 opacity-30">&#9888;</div>
        <h2 className="text-lg font-semibold text-surface-900 mb-2">Setup Error</h2>
        <p className="text-sm text-surface-500 mb-4">
          {error.message || "Something went wrong during onboarding."}
        </p>
        <button onClick={reset} className="btn-primary text-sm px-6 py-2">
          Try again
        </button>
      </div>
    </div>
  );
}

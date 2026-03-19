"use client";

export function ContextBlock({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-2xs font-medium text-surface-400 uppercase">{label}</div>
      <div className="text-sm text-surface-700 mt-0.5">{value}</div>
    </div>
  );
}

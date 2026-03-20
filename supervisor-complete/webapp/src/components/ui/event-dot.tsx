"use client";

export function EventDot({ type }: { type: string }) {
  let color = "bg-surface-300";
  if (type.includes("completed")) color = "bg-emerald-500";
  else if (type.includes("started")) color = "bg-blue-500";
  else if (type.includes("failed") || type.includes("error")) color = "bg-red-500";
  else if (type.includes("approval")) color = "bg-amber-500";
  else if (type.includes("tool")) color = "bg-violet-500";
  return <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${color}`} />;
}

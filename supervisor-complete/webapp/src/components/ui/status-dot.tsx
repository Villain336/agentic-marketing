"use client";

import type { AgentStatus } from "@/types";

export const STATUS_COLORS: Record<AgentStatus, string> = {
  idle: "bg-surface-200",
  queued: "bg-amber-300",
  running: "bg-brand-500 animate-pulse",
  done: "bg-emerald-500",
  error: "bg-red-500",
};

export const GRADE_COLORS: Record<string, string> = {
  "A+": "bg-emerald-100 text-emerald-700",
  A: "bg-emerald-100 text-emerald-700",
  "A-": "bg-emerald-50 text-emerald-600",
  "B+": "bg-blue-100 text-blue-700",
  B: "bg-blue-100 text-blue-700",
  "B-": "bg-blue-50 text-blue-600",
  "C+": "bg-amber-100 text-amber-700",
  C: "bg-amber-100 text-amber-700",
  "C-": "bg-amber-50 text-amber-600",
  D: "bg-red-100 text-red-700",
  "D-": "bg-red-100 text-red-700",
  F: "bg-red-200 text-red-800",
  "—": "bg-surface-100 text-surface-400",
};

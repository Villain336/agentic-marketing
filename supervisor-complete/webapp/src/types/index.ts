// ── Agent & Campaign Types ──────────────────────────────────────────────

export type AgentStatus = "idle" | "queued" | "running" | "done" | "error";
export type Grade = "A+" | "A" | "A-" | "B+" | "B" | "B-" | "C+" | "C" | "C-" | "D" | "D-" | "F" | "—";

export interface AgentDef {
  id: string;
  label: string;
  role: string;
  department: Department;
  icon: string;
  toolCount: number;
  realTools: number;
}

export type Department =
  | "marketing"
  | "sales"
  | "operations"
  | "finance"
  | "legal"
  | "engineering"
  | "intelligence";

export interface DepartmentDef {
  id: Department;
  label: string;
  description: string;
  color: string;
  icon: string;
}

export interface AgentRun {
  agentId: string;
  status: AgentStatus;
  output: string;
  grade: Grade;
  score: number;
  phases: string[];
  startedAt?: string;
  completedAt?: string;
  duration?: number;
  provider?: string;
  model?: string;
}

export interface BusinessProfile {
  name: string;
  service: string;
  icp: string;
  geography: string;
  goal: string;
  entityType: string;
  industry: string;
  founderTitle: string;
  brandContext: string;
}

export interface Campaign {
  id: string;
  userId: string;
  status: "active" | "paused" | "complete";
  agentRuns: Record<string, AgentRun>;
  business: BusinessProfile;
  createdAt: string;
}

// ── SSE Event Types ─────────────────────────────────────────────────────

export interface SSEEvent {
  event: "think" | "tool_call" | "tool_result" | "output" | "error" | "status";
  content?: string;
  tool_name?: string;
  tool_input?: Record<string, unknown>;
  tool_output?: string;
  memory_update?: Record<string, unknown>;
  provider?: string;
  model?: string;
  agent_id?: string;
}

// ── Onboarding Types ────────────────────────────────────────────────────

export type OnboardingStage =
  | "welcome"
  | "business"
  | "entity"
  | "revenue"
  | "channels"
  | "autonomy"
  | "provisioning";

export interface OnboardingData {
  stage: OnboardingStage;
  business: Partial<BusinessProfile>;
  channels: Record<string, boolean>;
  autonomyLevel: "full" | "guided" | "collaborative";
}

// ── Pricing Types ───────────────────────────────────────────────────────

export interface PricingTier {
  id: string;
  name: string;
  price: number;
  originalPrice: number;
  period: string;
  description: string;
  features: string[];
  agentCount: number;
  highlight?: boolean;
  cta: string;
}

// ── User Session ────────────────────────────────────────────────────────

export interface UserSession {
  accessToken: string;
  userId: string;
  email: string;
  plan: string;
  agencyName: string;
}

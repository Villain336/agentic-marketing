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
  websiteUrl: string;
  pricingModel: string;
  currentRevenue: string;
  teamSize: string;
  competitors: string;
  biggestChallenge: string;
  brandVoice: string;
  businessModel: string;
  startingFromScratch: boolean;
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
  | "idea_discovery"
  | "market_validation"
  | "model_selection"
  | "business"
  | "entity"
  | "revenue"
  | "channels"
  | "integrations"
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

// ── Autonomy & Settings Types ────────────────────────────────────────────

export interface AutonomySettingsResponse {
  global_level: "autonomous" | "guided" | "human_override";
  spending_approval_threshold: number;
  outbound_approval_required: boolean;
  content_approval_required: boolean;
  infrastructure_approval_required: boolean;
  escalation_channel: string;
  per_agent: Record<string, AgentAutonomySettings>;
}

export interface AgentAutonomySettings {
  agent_id: string;
  autonomy_level: string;
  enabled: boolean;
  max_iterations: number;
  spending_limit: number;
  allowed_tools: string[];
  blocked_tools: string[];
  auto_approve_tools: string[];
  notes: string;
}

export interface EventEntry {
  id: string;
  type: string;
  source_agent: string;
  campaign_id: string;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface TriggerRule {
  id: string;
  name: string;
  event_type: string;
  source_agent: string;
  condition: Record<string, unknown>;
  action: string;
  target_agent: string;
  target_data: Record<string, unknown>;
  enabled: boolean;
  cooldown_seconds: number;
}

export interface ApprovalItemResponse {
  id: string;
  campaign_id: string;
  agent_id: string;
  action_type: string;
  content: Record<string, unknown>;
  status: string;
  decided_by: string;
  created_at: string;
}

// ── User Session ────────────────────────────────────────────────────────

export interface UserSession {
  accessToken: string;
  userId: string;
  email: string;
  plan: string;
  agencyName: string;
}

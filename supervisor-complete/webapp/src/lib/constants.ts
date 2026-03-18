import type { AgentDef, DepartmentDef, PricingTier } from "@/types";

// ── Departments ─────────────────────────────────────────────────────────

export const DEPARTMENTS: DepartmentDef[] = [
  {
    id: "marketing",
    label: "Marketing",
    description: "Content, social, ads, SEO, newsletters",
    color: "bg-violet-100 text-violet-700 border-violet-200",
    icon: "Megaphone",
  },
  {
    id: "sales",
    label: "Sales",
    description: "Prospecting, outreach, pipeline, CRM",
    color: "bg-blue-100 text-blue-700 border-blue-200",
    icon: "Handshake",
  },
  {
    id: "operations",
    label: "Operations",
    description: "Client success, procurement, site, analytics",
    color: "bg-emerald-100 text-emerald-700 border-emerald-200",
    icon: "Settings",
  },
  {
    id: "finance",
    label: "Finance",
    description: "Billing, treasury, tax, financial planning",
    color: "bg-amber-100 text-amber-700 border-amber-200",
    icon: "DollarSign",
  },
  {
    id: "legal",
    label: "Legal & Compliance",
    description: "Contracts, compliance, governance, privacy",
    color: "bg-slate-100 text-slate-700 border-slate-200",
    icon: "Scale",
  },
  {
    id: "engineering",
    label: "Engineering",
    description: "Full-stack dev, infrastructure, security",
    color: "bg-cyan-100 text-cyan-700 border-cyan-200",
    icon: "Code",
  },
  {
    id: "intelligence",
    label: "Intelligence",
    description: "Research, competitive intel, analytics, genome",
    color: "bg-rose-100 text-rose-700 border-rose-200",
    icon: "Brain",
  },
];

// ── Agents ──────────────────────────────────────────────────────────────

export const AGENTS: AgentDef[] = [
  // Marketing
  { id: "content", label: "Content", role: "Pillar content & supporting articles", department: "marketing", icon: "FileText", toolCount: 12, realTools: 8 },
  { id: "social", label: "Social Media", role: "Calendar, posts, engagement", department: "marketing", icon: "Share2", toolCount: 10, realTools: 7 },
  { id: "ads", label: "Ad Creative", role: "Meta + Google ad variants", department: "marketing", icon: "Image", toolCount: 8, realTools: 5 },
  { id: "ppc", label: "PPC Manager", role: "Weekly campaign optimization", department: "marketing", icon: "Target", toolCount: 8, realTools: 5 },
  { id: "newsletter", label: "Newsletter", role: "Email list strategy & sequences", department: "marketing", icon: "Mail", toolCount: 6, realTools: 4 },
  { id: "seo", label: "SEO", role: "Keyword research & backlink strategy", department: "marketing", icon: "Search", toolCount: 6, realTools: 5 },
  { id: "design_director", label: "Design", role: "Brand system & visual identity", department: "marketing", icon: "Palette", toolCount: 4, realTools: 2 },

  // Sales
  { id: "prospector", label: "Prospector", role: "Find & qualify leads", department: "sales", icon: "UserSearch", toolCount: 10, realTools: 8 },
  { id: "outreach", label: "Outreach", role: "Cold email sequences", department: "sales", icon: "Send", toolCount: 8, realTools: 6 },
  { id: "sales", label: "Sales Ops", role: "Pipeline & close strategies", department: "sales", icon: "TrendingUp", toolCount: 6, realTools: 3 },
  { id: "referral", label: "Referral", role: "Referral program & advocacy", department: "sales", icon: "Users", toolCount: 4, realTools: 2 },

  // Operations
  { id: "sitelaunch", label: "Site Launch", role: "Landing pages & deployment", department: "operations", icon: "Globe", toolCount: 8, realTools: 5 },
  { id: "cs", label: "Client Success", role: "Onboarding & retention", department: "operations", icon: "HeartHandshake", toolCount: 6, realTools: 3 },
  { id: "procurement", label: "Procurement", role: "Tool stack & vendor management", department: "operations", icon: "ShoppingCart", toolCount: 4, realTools: 2 },
  { id: "analytics_agent", label: "Analytics", role: "Dashboards & attribution", department: "operations", icon: "BarChart3", toolCount: 6, realTools: 3 },

  // Finance
  { id: "finance", label: "Finance", role: "Financial planning & cash flow", department: "finance", icon: "Calculator", toolCount: 6, realTools: 3 },
  { id: "billing", label: "Billing", role: "Invoicing & collections", department: "finance", icon: "Receipt", toolCount: 6, realTools: 4 },
  { id: "tax", label: "Tax", role: "Tax strategy & compliance", department: "finance", icon: "FileSpreadsheet", toolCount: 4, realTools: 2 },
  { id: "treasury", label: "Treasury", role: "Cash management & banking", department: "finance", icon: "Vault", toolCount: 4, realTools: 1 },

  // Legal
  { id: "legal", label: "Legal", role: "Contracts & compliance playbook", department: "legal", icon: "Scale", toolCount: 6, realTools: 3 },
  { id: "governance", label: "Governance", role: "Corporate governance & board", department: "legal", icon: "Building2", toolCount: 4, realTools: 1 },
  { id: "hr", label: "HR", role: "Hiring playbook & policies", department: "legal", icon: "UserCog", toolCount: 4, realTools: 2 },

  // Engineering
  { id: "fullstack_dev", label: "Full-Stack Dev", role: "Code generation & deployment", department: "engineering", icon: "Code", toolCount: 8, realTools: 2 },
  { id: "enterprise_sec", label: "Security", role: "Threat modeling & compliance", department: "engineering", icon: "Shield", toolCount: 6, realTools: 1 },

  // Intelligence
  { id: "marketing_expert", label: "GTM Strategy", role: "Go-to-market & positioning", department: "intelligence", icon: "Compass", toolCount: 8, realTools: 5 },
  { id: "competitive_intel", label: "Competitive Intel", role: "Market landscape & threats", department: "intelligence", icon: "Radar", toolCount: 6, realTools: 4 },
  { id: "supervisor", label: "Supervisor", role: "Executive briefing & coordination", department: "intelligence", icon: "Crown", toolCount: 4, realTools: 2 },
];

export function getAgentsByDepartment(dept: string): AgentDef[] {
  return AGENTS.filter((a) => a.department === dept);
}

// ── Pricing ─────────────────────────────────────────────────────────────

export const PRICING_TIERS: PricingTier[] = [
  {
    id: "starter",
    name: "Starter",
    price: 1250,
    originalPrice: 2500,
    period: "month",
    description: "For solo founders ready to automate their go-to-market",
    agentCount: 15,
    features: [
      "15 core agents",
      "5,000 LLM calls/month",
      "Email + social + content",
      "Basic analytics dashboard",
      "Community support",
    ],
    cta: "Start Building",
  },
  {
    id: "growth",
    name: "Growth",
    price: 3500,
    originalPrice: 7000,
    period: "month",
    description: "For growing teams that need the full operating system",
    agentCount: 30,
    highlight: true,
    features: [
      "30 agents across all departments",
      "25,000 LLM calls/month",
      "Full tool integrations",
      "Cross-campaign genome learning",
      "Priority support + Slack",
      "Custom agent training",
    ],
    cta: "Scale Up",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 7500,
    originalPrice: 15000,
    period: "month",
    description: "For organizations running multiple campaigns at scale",
    agentCount: 44,
    features: [
      "All 44 agents + custom agents",
      "Unlimited LLM calls",
      "On-prem deployment option",
      "SSO + RBAC + audit logs",
      "Dedicated success manager",
      "SLA guarantee",
      "White-label option",
    ],
    cta: "Contact Sales",
  },
];

// ── Onboarding Stages ───────────────────────────────────────────────────

export const ONBOARDING_STAGES = [
  { id: "welcome", label: "Welcome", icon: "Sparkles" },
  { id: "business", label: "Your Business", icon: "Building" },
  { id: "entity", label: "Legal Entity", icon: "FileCheck" },
  { id: "revenue", label: "Revenue Goals", icon: "Target" },
  { id: "channels", label: "Channels", icon: "Plug" },
  { id: "autonomy", label: "Control Level", icon: "Sliders" },
  { id: "provisioning", label: "Building...", icon: "Rocket" },
] as const;

// ── API Config ──────────────────────────────────────────────────────────

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

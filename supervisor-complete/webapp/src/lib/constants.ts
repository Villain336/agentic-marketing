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
    description: "Full-stack dev, AI coding, infrastructure, security",
    color: "bg-cyan-100 text-cyan-700 border-cyan-200",
    icon: "Code",
  },
  {
    id: "intelligence",
    label: "Intelligence",
    description: "Web crawling, competitive intel, market analysis",
    color: "bg-rose-100 text-rose-700 border-rose-200",
    icon: "Brain",
  },
];

// ── Agents ──────────────────────────────────────────────────────────────

export const AGENTS: AgentDef[] = [
  // Marketing
  { id: "content", label: "Content", role: "SEO content & authority building", department: "marketing", icon: "FileText", toolCount: 15, realTools: 12 },
  { id: "social", label: "Social Media", role: "Calendar, posts, engagement", department: "marketing", icon: "Share2", toolCount: 14, realTools: 11 },
  { id: "ads", label: "Ad Creative", role: "Meta + Google ad campaigns", department: "marketing", icon: "Image", toolCount: 12, realTools: 9 },
  { id: "ppc", label: "PPC Manager", role: "Campaign optimization & bidding", department: "marketing", icon: "Target", toolCount: 12, realTools: 9 },
  { id: "newsletter", label: "Newsletter", role: "Email sequences & list growth", department: "marketing", icon: "Mail", toolCount: 10, realTools: 8 },
  { id: "seo", label: "SEO", role: "Keyword research & backlinks", department: "marketing", icon: "Search", toolCount: 10, realTools: 8 },
  { id: "design_director", label: "Design", role: "Brand system & visual identity", department: "marketing", icon: "Palette", toolCount: 8, realTools: 6 },

  // Sales
  { id: "prospector", label: "Prospector", role: "Find & qualify leads with real data", department: "sales", icon: "UserSearch", toolCount: 14, realTools: 12 },
  { id: "outreach", label: "Outreach", role: "Cold email & SMS sequences", department: "sales", icon: "Send", toolCount: 12, realTools: 10 },
  { id: "sales", label: "Sales Ops", role: "Pipeline management & CRM", department: "sales", icon: "TrendingUp", toolCount: 10, realTools: 7 },
  { id: "referral", label: "Referral", role: "Referral programs & advocacy", department: "sales", icon: "Users", toolCount: 8, realTools: 6 },

  // Operations
  { id: "sitelaunch", label: "Site Launch", role: "Deploy sites & landing pages", department: "operations", icon: "Globe", toolCount: 12, realTools: 9 },
  { id: "cs", label: "Client Success", role: "Onboarding & retention", department: "operations", icon: "HeartHandshake", toolCount: 10, realTools: 7 },
  { id: "procurement", label: "Procurement", role: "Tool stack & vendor management", department: "operations", icon: "ShoppingCart", toolCount: 8, realTools: 6 },
  { id: "analytics_agent", label: "Analytics", role: "Dashboards & attribution", department: "operations", icon: "BarChart3", toolCount: 10, realTools: 7 },

  // Finance
  { id: "finance", label: "Finance", role: "Financial planning & cash flow", department: "finance", icon: "Calculator", toolCount: 10, realTools: 7 },
  { id: "billing", label: "Billing", role: "Invoicing & payment collection", department: "finance", icon: "Receipt", toolCount: 10, realTools: 8 },
  { id: "tax", label: "Tax", role: "Tax strategy & compliance", department: "finance", icon: "FileSpreadsheet", toolCount: 8, realTools: 6 },
  { id: "treasury", label: "Treasury", role: "Cash management & banking", department: "finance", icon: "Vault", toolCount: 8, realTools: 5 },

  // Legal
  { id: "legal", label: "Legal", role: "Contracts & compliance", department: "legal", icon: "Scale", toolCount: 10, realTools: 7 },
  { id: "governance", label: "Governance", role: "Corporate governance & board", department: "legal", icon: "Building2", toolCount: 8, realTools: 5 },
  { id: "hr", label: "HR", role: "Hiring playbook & policies", department: "legal", icon: "UserCog", toolCount: 8, realTools: 6 },

  // Engineering
  { id: "fullstack_dev", label: "Full-Stack Dev", role: "AI-powered code generation & deploy", department: "engineering", icon: "Code", toolCount: 16, realTools: 12 },
  { id: "enterprise_sec", label: "Security", role: "Threat modeling & compliance", department: "engineering", icon: "Shield", toolCount: 10, realTools: 5 },

  // Intelligence
  { id: "marketing_expert", label: "GTM Strategy", role: "Go-to-market & positioning", department: "intelligence", icon: "Compass", toolCount: 12, realTools: 9 },
  { id: "competitive_intel", label: "Competitive Intel", role: "Web crawling & market analysis", department: "intelligence", icon: "Radar", toolCount: 12, realTools: 10 },
  { id: "supervisor", label: "Omni OS", role: "Executive briefing & coordination", department: "intelligence", icon: "Crown", toolCount: 8, realTools: 6 },
];

export function getAgentsByDepartment(dept: string): AgentDef[] {
  return AGENTS.filter((a) => a.department === dept);
}

// ── Launch Agents (10 ship first) ───────────────────────────────────────

export const LAUNCH_AGENTS = {
  mustHave: ["prospector", "outreach", "content", "social", "billing"],
  differentiators: ["fullstack_dev", "sitelaunch", "competitive_intel", "analytics_agent", "newsletter"],
};

// ── Features for landing page ───────────────────────────────────────────

export const FEATURES = [
  {
    id: "autonomous-agents",
    title: "44 Autonomous Agents",
    description: "Every agent has real API integrations — not wrappers. Prospector finds real leads, Outreach sends real emails, Billing collects real money.",
    icon: "cpu",
  },
  {
    id: "claude-sdk",
    title: "Claude AI Code Engine",
    description: "Every agent can generate, review, and deploy production code using the Claude Agent SDK. Ship features, fix bugs, build MVPs — autonomously.",
    icon: "code",
  },
  {
    id: "web-crawlers",
    title: "Cloudflare Web Crawlers",
    description: "Real-time competitive intelligence with Cloudflare Browser Rendering. Monitor competitor pricing, features, and content automatically.",
    icon: "globe",
  },
  {
    id: "multi-model",
    title: "5 LLM Providers",
    description: "Automatic failover across Anthropic, OpenAI, Google, AWS Bedrock, and OpenRouter. Circuit breakers ensure 99.9% uptime.",
    icon: "layers",
  },
  {
    id: "revenue-loop",
    title: "Revenue Autopilot",
    description: "Prospector to Outreach to Billing: the complete revenue loop runs autonomously. Find leads, send sequences, collect payments.",
    icon: "zap",
  },
  {
    id: "deploy-sites",
    title: "Ship Sites & Apps",
    description: "Full-stack dev agent writes code, Site Launch deploys to Vercel or Cloudflare, registers domains, sets up analytics — in minutes.",
    icon: "rocket",
  },
];

// ── Integrations ────────────────────────────────────────────────────────

export const INTEGRATIONS = [
  "Apollo", "SendGrid", "Stripe", "Vercel", "Cloudflare", "HubSpot",
  "Twitter/X", "LinkedIn", "Instagram", "Reddit", "Buffer", "Google Ads",
  "Meta Ads", "Twilio", "Cal.com", "Slack", "Telegram", "Figma",
  "ConvertKit", "Beehiiv", "GitHub", "Snyk", "DocuSign", "PandaDoc",
  "Google Analytics", "Plausible", "Namecheap", "E2B", "VAPI", "Bland.ai",
];

// ── Pricing ─────────────────────────────────────────────────────────────

export const PRICING_TIERS: PricingTier[] = [
  {
    id: "starter",
    name: "Starter",
    price: 497,
    originalPrice: 997,
    period: "month",
    description: "For solo founders ready to automate their go-to-market",
    agentCount: 10,
    features: [
      "10 core agents (the launch pack)",
      "5,000 AI operations/month",
      "Prospector + Outreach + Billing loop",
      "Social media automation",
      "Basic analytics dashboard",
      "Community support",
    ],
    cta: "Start Building",
  },
  {
    id: "growth",
    name: "Growth",
    price: 1497,
    originalPrice: 2997,
    period: "month",
    description: "For growing teams that need the full operating system",
    agentCount: 27,
    highlight: true,
    features: [
      "27 agents across all departments",
      "25,000 AI operations/month",
      "Claude SDK code generation",
      "Cloudflare web crawlers",
      "Full API integrations",
      "Cross-campaign intelligence",
      "Priority support + Slack",
    ],
    cta: "Scale Up",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    price: 4997,
    originalPrice: 9997,
    period: "month",
    description: "For organizations running operations at scale",
    agentCount: 44,
    features: [
      "All 44 agents + custom agents",
      "Unlimited AI operations",
      "Self-hosted deployment option",
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
  { id: "integrations", label: "API Keys", icon: "Key" },
  { id: "autonomy", label: "Control Level", icon: "Sliders" },
  { id: "provisioning", label: "Building...", icon: "Rocket" },
] as const;

// ── API Config ──────────────────────────────────────────────────────────

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
export const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

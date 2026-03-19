"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Rocket, Target, Users, Sparkles, Check, Loader2 } from "lucide-react";
import type { OnboardingStage, BusinessProfile } from "@/types";
import { ONBOARDING_STAGES } from "@/lib/constants";
import { api } from "@/lib/api";

const AUTONOMY_ICONS: Record<string, React.ReactNode> = {
  Rocket: <Rocket className="w-6 h-6" />,
  Target: <Target className="w-6 h-6" />,
  Users: <Users className="w-6 h-6" />,
};

const ENTITY_TYPES = [
  { value: "sole_prop", label: "Sole Proprietorship", desc: "Simplest structure, personal liability" },
  { value: "llc", label: "LLC", desc: "Limited liability, flexible taxation" },
  { value: "s_corp", label: "S-Corp", desc: "Tax advantages for profitable businesses" },
  { value: "c_corp", label: "C-Corp", desc: "Needed for VC fundraising" },
  { value: "partnership", label: "Partnership", desc: "Multiple co-founders" },
];

const CHANNELS = [
  { id: "domain", label: "Website / Domain", desc: "Your web presence" },
  { id: "email", label: "Email (SendGrid)", desc: "Outreach & newsletters" },
  { id: "linkedin", label: "LinkedIn", desc: "B2B social selling" },
  { id: "twitter", label: "Twitter / X", desc: "Thought leadership" },
  { id: "crm", label: "CRM (HubSpot)", desc: "Pipeline management" },
  { id: "payments", label: "Payments (Stripe)", desc: "Invoicing & billing" },
];

const AUTONOMY_LEVELS = [
  { value: "full", label: "Full Autonomy", desc: "Agents execute independently. You review weekly.", icon: "Rocket" },
  { value: "guided", label: "Guided Autonomy", desc: "Agents draft, you approve key decisions. Best for most.", icon: "Target" },
  { value: "collaborative", label: "Collaborative", desc: "Step-by-step with your input at every stage.", icon: "Users" },
];

const API_KEY_FIELDS = [
  { id: "SENDGRID_API_KEY", label: "SendGrid API Key", channel: "email", placeholder: "SG.xxxxx", desc: "For sending emails and sequences" },
  { id: "HUBSPOT_API_KEY", label: "HubSpot API Key", channel: "crm", placeholder: "pat-xxxxx", desc: "For CRM contact management" },
  { id: "STRIPE_API_KEY", label: "Stripe Secret Key", channel: "payments", placeholder: "sk_live_xxxxx", desc: "For invoicing and billing" },
  { id: "SERPER_API_KEY", label: "Serper API Key", channel: "", placeholder: "xxxxx", desc: "For web search (prospecting, research)" },
  { id: "TWITTER_BEARER_TOKEN", label: "Twitter Bearer Token", channel: "twitter", placeholder: "AAAAAxxxxx", desc: "For posting and social listening" },
  { id: "APOLLO_API_KEY", label: "Apollo.io API Key", channel: "", placeholder: "xxxxx", desc: "For finding contacts and leads" },
  { id: "OPENAI_API_KEY", label: "OpenAI API Key", channel: "", placeholder: "sk-xxxxx", desc: "For image generation (DALL-E)" },
  { id: "VERCEL_TOKEN", label: "Vercel Token", channel: "domain", placeholder: "xxxxx", desc: "For website deployment" },
];

export default function OnboardingPage() {
  const router = useRouter();
  const [stage, setStage] = useState<OnboardingStage>("welcome");
  const [business, setBusiness] = useState<Partial<BusinessProfile>>({
    name: "",
    service: "",
    icp: "",
    geography: "USA",
    goal: "",
    entityType: "llc",
    industry: "",
    founderTitle: "CEO",
    brandContext: "",
  });
  const [channels, setChannels] = useState<Record<string, boolean>>({});
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({});
  const [autonomy, setAutonomy] = useState("guided");
  const [provisionIdx, setProvisionIdx] = useState(0);

  const currentIdx = ONBOARDING_STAGES.findIndex((s) => s.id === stage);
  const progress = Math.round(((currentIdx + 1) / ONBOARDING_STAGES.length) * 100);

  const update = useCallback((field: string, value: string) => {
    setBusiness((prev) => ({ ...prev, [field]: value }));
  }, []);

  const next = useCallback(() => {
    const stages: OnboardingStage[] = ["welcome", "business", "entity", "revenue", "channels", "integrations", "autonomy", "provisioning"];
    const idx = stages.indexOf(stage);
    if (idx < stages.length - 1) {
      setStage(stages[idx + 1]);
    }
  }, [stage]);

  const prev = useCallback(() => {
    const stages: OnboardingStage[] = ["welcome", "business", "entity", "revenue", "channels", "integrations", "autonomy", "provisioning"];
    const idx = stages.indexOf(stage);
    if (idx > 0) {
      setStage(stages[idx - 1]);
    }
  }, [stage]);

  const startProvisioning = useCallback(() => {
    setStage("provisioning");
    localStorage.setItem("sv_business", JSON.stringify(business));
    localStorage.setItem("sv_channels", JSON.stringify(channels));
    localStorage.setItem("sv_autonomy", autonomy);

    // Send API keys to backend securely — never store in localStorage
    const nonEmptyKeys = Object.fromEntries(
      Object.entries(apiKeys).filter(([, v]) => v.trim())
    );
    if (Object.keys(nonEmptyKeys).length > 0) {
      api.post("/settings/secrets", { keys: nonEmptyKeys }).catch(() => {
        // Secrets will need to be configured later via Settings
      });
    }

    // Animate provisioning
    const items = ["Agents", "Tools", "Integrations", "Genome", "Scheduler", "Dashboard"];
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setProvisionIdx(i);
      if (i >= items.length) {
        clearInterval(interval);
        setTimeout(() => router.push("/dashboard"), 800);
      }
    }, 600);
  }, [business, channels, apiKeys, autonomy, router]);

  return (
    <div className="min-h-screen bg-white flex flex-col">
      {/* Progress bar */}
      <div className="h-1 bg-surface-100">
        <div
          className="h-full bg-brand-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Stage indicators */}
      <div className="flex justify-center gap-2 pt-8 pb-2">
        {ONBOARDING_STAGES.map((s, i) => (
          <div
            key={s.id}
            className={`w-2 h-2 rounded-full transition-all duration-300 ${
              i <= currentIdx ? "bg-brand-500 scale-100" : "bg-surface-200 scale-75"
            }`}
          />
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="w-full max-w-lg animate-fade-in">
          {stage === "welcome" && <WelcomeStage onNext={next} name={business.name || ""} onNameChange={(v) => update("name", v)} />}
          {stage === "business" && <BusinessStage business={business} onChange={update} onNext={next} onBack={prev} />}
          {stage === "entity" && <EntityStage value={business.entityType || "llc"} onChange={(v) => update("entityType", v)} onNext={next} onBack={prev} />}
          {stage === "revenue" && <RevenueStage business={business} onChange={update} onNext={next} onBack={prev} />}
          {stage === "channels" && <ChannelsStage channels={channels} onChange={setChannels} onNext={next} onBack={prev} />}
          {stage === "integrations" && <IntegrationsStage apiKeys={apiKeys} onChange={setApiKeys} channels={channels} onNext={next} onBack={prev} />}
          {stage === "autonomy" && <AutonomyStage value={autonomy} onChange={setAutonomy} onNext={startProvisioning} onBack={prev} />}
          {stage === "provisioning" && <ProvisioningStage idx={provisionIdx} name={business.name || "your business"} />}
        </div>
      </div>
    </div>
  );
}

// ── Stage Components ────────────────────────────────────────────────────

function WelcomeStage({ onNext, name, onNameChange }: { onNext: () => void; name: string; onNameChange: (v: string) => void }) {
  return (
    <div className="text-center">
      <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-6">
        <Sparkles className="w-8 h-8 text-brand-500" />
      </div>
      <h1 className="font-display font-bold text-3xl text-surface-900 mb-3">
        Let&apos;s build your AI team
      </h1>
      <p className="text-surface-500 mb-8 leading-relaxed">
        In 5 minutes, you&apos;ll have 44 agents working for you.
        <br />No technical setup required.
      </p>
      <div className="max-w-sm mx-auto mb-8">
        <label className="block text-sm font-medium text-surface-700 mb-1.5 text-left">
          What&apos;s your company called?
        </label>
        <input
          type="text"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder="Acme Growth Co"
          className="input-field text-center text-lg"
          autoFocus
        />
      </div>
      <button onClick={onNext} className="btn-primary px-10 py-3" disabled={!name.trim()}>
        Let&apos;s Go
      </button>
    </div>
  );
}

function BusinessStage({
  business,
  onChange,
  onNext,
  onBack,
}: {
  business: Partial<BusinessProfile>;
  onChange: (f: string, v: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const canProceed = business.service && business.icp;
  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">Tell us about {business.name || "your business"}</h2>
      <p className="text-surface-500 text-sm mb-8">This powers every agent&apos;s context. Be specific — the more detail, the better your outputs.</p>
      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">What do you sell?</label>
          <input
            value={business.service || ""}
            onChange={(e) => onChange("service", e.target.value)}
            placeholder="e.g., AI-powered CRM for real estate teams"
            className="input-field"
            autoFocus
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">Who&apos;s your ideal customer?</label>
          <input
            value={business.icp || ""}
            onChange={(e) => onChange("icp", e.target.value)}
            placeholder="e.g., Real estate brokerages with 10-50 agents"
            className="input-field"
          />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Industry</label>
            <input
              value={business.industry || ""}
              onChange={(e) => onChange("industry", e.target.value)}
              placeholder="e.g., PropTech"
              className="input-field"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Geography</label>
            <input
              value={business.geography || ""}
              onChange={(e) => onChange("geography", e.target.value)}
              placeholder="e.g., North America"
              className="input-field"
            />
          </div>
        </div>
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary" disabled={!canProceed}>Continue</button>
      </div>
    </div>
  );
}

function EntityStage({ value, onChange, onNext, onBack }: { value: string; onChange: (v: string) => void; onNext: () => void; onBack: () => void }) {
  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">Legal entity type</h2>
      <p className="text-surface-500 text-sm mb-8">This customizes your legal, tax, and compliance agents.</p>
      <div className="space-y-3">
        {ENTITY_TYPES.map((e) => (
          <button
            key={e.value}
            onClick={() => onChange(e.value)}
            className={`w-full text-left p-4 rounded-xl border-2 transition-all ${
              value === e.value
                ? "border-brand-500 bg-brand-50"
                : "border-surface-200 hover:border-surface-300"
            }`}
          >
            <div className="font-medium text-surface-900">{e.label}</div>
            <div className="text-xs text-surface-500 mt-0.5">{e.desc}</div>
          </button>
        ))}
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary">Continue</button>
      </div>
    </div>
  );
}

function RevenueStage({
  business,
  onChange,
  onNext,
  onBack,
}: {
  business: Partial<BusinessProfile>;
  onChange: (f: string, v: string) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">Revenue goals</h2>
      <p className="text-surface-500 text-sm mb-8">Your finance and sales agents will calibrate around these targets.</p>
      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">90-day revenue target</label>
          <input
            value={business.goal || ""}
            onChange={(e) => onChange("goal", e.target.value)}
            placeholder="e.g., $100,000"
            className="input-field"
            autoFocus
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">Your title</label>
          <input
            value={business.founderTitle || ""}
            onChange={(e) => onChange("founderTitle", e.target.value)}
            placeholder="e.g., CEO, Founder, Managing Partner"
            className="input-field"
          />
        </div>
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary">Continue</button>
      </div>
    </div>
  );
}

function ChannelsStage({
  channels,
  onChange,
  onNext,
  onBack,
}: {
  channels: Record<string, boolean>;
  onChange: (c: Record<string, boolean>) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const toggle = (id: string) => onChange({ ...channels, [id]: !channels[id] });
  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">Active channels</h2>
      <p className="text-surface-500 text-sm mb-8">Select what you already have set up. Agents will configure the rest.</p>
      <div className="space-y-3">
        {CHANNELS.map((ch) => (
          <button
            key={ch.id}
            onClick={() => toggle(ch.id)}
            className={`w-full text-left p-4 rounded-xl border-2 flex items-center gap-4 transition-all ${
              channels[ch.id]
                ? "border-brand-500 bg-brand-50"
                : "border-surface-200 hover:border-surface-300"
            }`}
          >
            <div className={`w-5 h-5 rounded-md border-2 flex items-center justify-center transition-all ${
              channels[ch.id] ? "bg-brand-500 border-brand-500" : "border-surface-300"
            }`}>
              {channels[ch.id] && <span className="text-white text-xs">&#10003;</span>}
            </div>
            <div className="flex-1">
              <div className="font-medium text-surface-900 text-sm">{ch.label}</div>
              <div className="text-xs text-surface-500">{ch.desc}</div>
            </div>
          </button>
        ))}
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary">Continue</button>
      </div>
    </div>
  );
}

function IntegrationsStage({
  apiKeys,
  onChange,
  channels,
  onNext,
  onBack,
}: {
  apiKeys: Record<string, string>;
  onChange: (keys: Record<string, string>) => void;
  channels: Record<string, boolean>;
  onNext: () => void;
  onBack: () => void;
}) {
  const relevantFields = API_KEY_FIELDS.filter(
    (f) => !f.channel || channels[f.channel]
  );
  const setKey = (id: string, value: string) => onChange({ ...apiKeys, [id]: value });

  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">Connect your tools</h2>
      <p className="text-surface-500 text-sm mb-8">
        Paste API keys for the services you use. Skip any you don&apos;t have yet — agents will prompt you later.
      </p>
      <div className="space-y-4 max-h-[420px] overflow-y-auto pr-1">
        {relevantFields.map((field) => (
          <div key={field.id}>
            <label className="block text-sm font-medium text-surface-700 mb-1">{field.label}</label>
            <input
              type="password"
              value={apiKeys[field.id] || ""}
              onChange={(e) => setKey(field.id, e.target.value)}
              placeholder={field.placeholder}
              className="input-field text-sm"
            />
            <p className="text-xs text-surface-400 mt-0.5">{field.desc}</p>
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary">Continue</button>
      </div>
    </div>
  );
}

function AutonomyStage({ value, onChange, onNext, onBack }: { value: string; onChange: (v: string) => void; onNext: () => void; onBack: () => void }) {
  return (
    <div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">How autonomous should agents be?</h2>
      <p className="text-surface-500 text-sm mb-8">You can change this anytime from your dashboard.</p>
      <div className="space-y-3">
        {AUTONOMY_LEVELS.map((level) => (
          <button
            key={level.value}
            onClick={() => onChange(level.value)}
            className={`w-full text-left p-5 rounded-xl border-2 transition-all ${
              value === level.value
                ? "border-brand-500 bg-brand-50"
                : "border-surface-200 hover:border-surface-300"
            }`}
          >
            <div className="flex items-center gap-3">
              <span className="text-brand-600">{AUTONOMY_ICONS[level.icon] || level.icon}</span>
              <div>
                <div className="font-medium text-surface-900">{level.label}</div>
                <div className="text-xs text-surface-500 mt-0.5">{level.desc}</div>
              </div>
            </div>
            {level.value === "guided" && (
              <div className="mt-2 ml-11 badge bg-brand-100 text-brand-700 text-2xs">Recommended</div>
            )}
          </button>
        ))}
      </div>
      <div className="flex justify-between mt-8">
        <button onClick={onBack} className="btn-ghost">Back</button>
        <button onClick={onNext} className="btn-primary">Launch Supervisor</button>
      </div>
    </div>
  );
}

function ProvisioningStage({ idx, name }: { idx: number; name: string }) {
  const items = ["Deploying Agents", "Connecting Tools", "Wiring Integrations", "Initializing Genome", "Starting Scheduler", "Building Dashboard"];
  return (
    <div className="text-center">
      <div className="w-16 h-16 rounded-2xl bg-brand-50 flex items-center justify-center mx-auto mb-6">
        <Rocket className="w-8 h-8 text-brand-500" />
      </div>
      <h2 className="font-display font-bold text-2xl text-surface-900 mb-2">
        Building {name}
      </h2>
      <p className="text-surface-500 text-sm mb-8">Setting up 44 agents and your operating infrastructure...</p>
      <div className="max-w-sm mx-auto space-y-3">
        {items.map((item, i) => (
          <div key={item} className={`flex items-center gap-3 transition-all duration-300 ${
            i <= idx ? "opacity-100" : "opacity-30"
          }`}>
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs transition-all ${
              i < idx ? "bg-emerald-100 text-emerald-600" : i === idx ? "bg-brand-100 text-brand-600 animate-pulse" : "bg-surface-100 text-surface-400"
            }`}>
              {i < idx ? <Check className="w-3 h-3" /> : i === idx ? <Loader2 className="w-3 h-3 animate-spin" /> : (i + 1)}
            </div>
            <span className={`text-sm ${i <= idx ? "text-surface-700 font-medium" : "text-surface-400"}`}>
              {item}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

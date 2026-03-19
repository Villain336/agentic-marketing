"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────

interface MarketplaceAgent {
  registration_id: string;
  agent_id: string;
  name: string;
  version: string;
  description: string;
  author: string;
  category: string;
  tags: string[];
  capabilities: string[];
  pricing_model: string;
  cost_per_run: number;
  installed_count: number;
  listed: boolean;
  approved: boolean;
}

interface MarketplaceItem {
  id: string;
  name: string;
  type: string;
  description: string;
  author: string;
  category: string;
  price: number;
  downloads: number;
  rating: number;
  tags: string[];
}

// ── Constants ──────────────────────────────────────────────────────────

const CATEGORIES = [
  { id: "all", label: "All" },
  { id: "marketing", label: "Marketing" },
  { id: "sales", label: "Sales" },
  { id: "operations", label: "Operations" },
  { id: "finance", label: "Finance" },
  { id: "legal", label: "Legal" },
  { id: "engineering", label: "Engineering" },
  { id: "intelligence", label: "Intelligence" },
  { id: "general", label: "General" },
];

const TABS = [
  { id: "browse", label: "Browse Agents" },
  { id: "installed", label: "Installed" },
  { id: "my-agents", label: "My Agents" },
] as const;

type TabId = typeof TABS[number]["id"];

// ── Page ───────────────────────────────────────────────────────────────

export default function MarketplacePage() {
  const router = useRouter();
  const [tab, setTab] = useState<TabId>("browse");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");
  const [agents, setAgents] = useState<MarketplaceAgent[]>([]);
  const [marketplaceItems, setMarketplaceItems] = useState<MarketplaceItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadAgents = useCallback(async () => {
    setLoading(true);
    try {
      // Load from both protocol registry and marketplace
      const [protocolRes, marketRes] = await Promise.allSettled([
        api.get<{ agents: MarketplaceAgent[] }>("/protocol/agents?listed_only=true"),
        api.get<{ items: MarketplaceItem[] }>("/marketplace/featured"),
      ]);

      if (protocolRes.status === "fulfilled") {
        setAgents(protocolRes.value.agents || []);
      }
      if (marketRes.status === "fulfilled") {
        setMarketplaceItems(marketRes.value.items || []);
      }
    } catch {
      // Backend offline
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const filteredAgents = agents.filter((a) => {
    if (category !== "all" && a.category !== category) return false;
    if (search && !a.name.toLowerCase().includes(search.toLowerCase()) &&
        !a.description.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  return (
    <div className="min-h-screen bg-surface-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-surface-200 flex items-center px-6 gap-4">
        <button onClick={() => router.push("/dashboard")} className="btn-ghost text-xs">
          &#8592; Dashboard
        </button>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">O</span>
          </div>
          <span className="font-display font-bold text-surface-900 text-sm">Marketplace</span>
        </div>
        <div className="flex-1" />
        <button
          onClick={() => router.push("/developer")}
          className="btn-secondary text-xs"
        >
          Developer Portal
        </button>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Hero */}
        <div className="text-center mb-10">
          <h1 className="font-display font-bold text-3xl text-surface-900 mb-3">
            Omni Agent Marketplace
          </h1>
          <p className="text-surface-500 max-w-lg mx-auto">
            Discover and install agents built by the community. Or publish your own and earn revenue.
          </p>
        </div>

        {/* Search */}
        <div className="max-w-xl mx-auto mb-8">
          <input
            type="text"
            placeholder="Search agents, tools, and integrations..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-field text-center"
          />
        </div>

        {/* Tabs */}
        <div className="flex justify-center gap-2 mb-6">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`badge text-xs transition-all ${
                tab === t.id ? "bg-surface-900 text-white" : "bg-surface-100 text-surface-500 hover:bg-surface-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Category Filter */}
        {tab === "browse" && (
          <div className="flex flex-wrap justify-center gap-1.5 mb-8">
            {CATEGORIES.map((c) => (
              <button
                key={c.id}
                onClick={() => setCategory(c.id)}
                className={`badge text-2xs transition-all ${
                  category === c.id
                    ? "bg-brand-100 text-brand-700"
                    : "bg-surface-100 text-surface-500 hover:bg-surface-200"
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        )}

        {/* Content */}
        {loading ? (
          <div className="text-center py-20 text-surface-400">Loading marketplace...</div>
        ) : tab === "browse" ? (
          <div>
            {/* Featured from marketplace backend */}
            {marketplaceItems.length > 0 && (
              <div className="mb-10">
                <h2 className="text-lg font-semibold text-surface-900 mb-4">Featured</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {marketplaceItems.map((item) => (
                    <MarketplaceCard key={item.id} item={item} />
                  ))}
                </div>
              </div>
            )}

            {/* Protocol-registered agents */}
            <h2 className="text-lg font-semibold text-surface-900 mb-4">
              Community Agents {filteredAgents.length > 0 && `(${filteredAgents.length})`}
            </h2>
            {filteredAgents.length === 0 ? (
              <div className="text-center py-16">
                <div className="text-4xl mb-4 opacity-20">&#128640;</div>
                <p className="text-surface-400 text-sm mb-4">
                  No agents published yet. Be the first!
                </p>
                <button onClick={() => router.push("/developer")} className="btn-primary text-sm">
                  Publish an Agent
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {filteredAgents.map((agent) => (
                  <AgentCard key={agent.agent_id} agent={agent} />
                ))}
              </div>
            )}
          </div>
        ) : tab === "installed" ? (
          <div className="text-center py-20">
            <div className="text-4xl mb-4 opacity-20">&#128230;</div>
            <p className="text-surface-400 text-sm">
              Installed agents will appear here.
            </p>
          </div>
        ) : (
          <div className="text-center py-20">
            <div className="text-4xl mb-4 opacity-20">&#128295;</div>
            <p className="text-surface-400 text-sm mb-4">
              Agents you&apos;ve built and published will appear here.
            </p>
            <button onClick={() => router.push("/developer")} className="btn-primary text-sm">
              Go to Developer Portal
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Cards ──────────────────────────────────────────────────────────────

function AgentCard({ agent }: { agent: MarketplaceAgent }) {
  return (
    <div className="card p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-surface-900 text-sm">{agent.name}</h3>
          <p className="text-2xs text-surface-400">by {agent.author || "Anonymous"} &middot; v{agent.version}</p>
        </div>
        <div className="badge text-2xs bg-surface-100 text-surface-500">{agent.category}</div>
      </div>
      <p className="text-xs text-surface-500 mb-3 line-clamp-2">{agent.description}</p>
      <div className="flex flex-wrap gap-1 mb-3">
        {agent.tags.slice(0, 3).map((tag) => (
          <span key={tag} className="badge text-2xs bg-brand-50 text-brand-600">{tag}</span>
        ))}
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-surface-400">{agent.installed_count} installs</span>
        <span className="font-medium text-surface-700">
          {agent.pricing_model === "free" ? "Free" : `$${agent.cost_per_run}/run`}
        </span>
      </div>
      <button className="btn-primary w-full mt-3 text-xs py-2">Install Agent</button>
    </div>
  );
}

function MarketplaceCard({ item }: { item: MarketplaceItem }) {
  return (
    <div className="card p-5 hover:shadow-md transition-shadow border-brand-100">
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-medium text-surface-900 text-sm">{item.name}</h3>
          <p className="text-2xs text-surface-400">by {item.author} &middot; {item.type}</p>
        </div>
        {item.rating > 0 && (
          <div className="text-xs text-amber-600 font-medium">
            &#9733; {item.rating.toFixed(1)}
          </div>
        )}
      </div>
      <p className="text-xs text-surface-500 mb-3 line-clamp-2">{item.description}</p>
      <div className="flex flex-wrap gap-1 mb-3">
        {item.tags.slice(0, 3).map((tag) => (
          <span key={tag} className="badge text-2xs bg-brand-50 text-brand-600">{tag}</span>
        ))}
      </div>
      <div className="flex items-center justify-between text-xs">
        <span className="text-surface-400">{item.downloads} downloads</span>
        <span className="font-medium text-surface-700">
          {item.price === 0 ? "Free" : `$${item.price}`}
        </span>
      </div>
      <button className="btn-primary w-full mt-3 text-xs py-2">Install</button>
    </div>
  );
}

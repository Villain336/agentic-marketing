"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────

interface APIKey {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  rate_limit: number;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  revoked: boolean;
}

interface WebhookSub {
  id: string;
  url: string;
  events: string[];
  active: boolean;
  created_at: string;
  failure_count: number;
  last_delivered_at: string;
  last_status_code: number;
}

interface OAuthApp {
  id: string;
  client_id: string;
  name: string;
  redirect_uris: string[];
  scopes: string[];
  created_at: string;
}

// ── Constants ──────────────────────────────────────────────────────────

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "api-keys", label: "API Keys" },
  { id: "webhooks", label: "Webhooks" },
  { id: "oauth", label: "OAuth Apps" },
  { id: "protocol", label: "Agent Protocol" },
] as const;

type TabId = typeof TABS[number]["id"];

// ── Page ───────────────────────────────────────────────────────────────

export default function DeveloperPage() {
  const router = useRouter();
  const [tab, setTab] = useState<TabId>("overview");
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [webhooks, setWebhooks] = useState<WebhookSub[]>([]);
  const [oauthApps, setOAuthApps] = useState<OAuthApp[]>([]);
  const [newKeyName, setNewKeyName] = useState("My API Key");
  const [newKeyResult, setNewKeyResult] = useState<string | null>(null);
  const [newWebhookUrl, setNewWebhookUrl] = useState("");
  const [newAppName, setNewAppName] = useState("");
  const [newAppRedirect, setNewAppRedirect] = useState("");
  const [newAppResult, setNewAppResult] = useState<{ clientId: string; clientSecret: string } | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [keysRes, whRes, oaRes] = await Promise.allSettled([
        api.get<{ keys: APIKey[] }>("/developer/api-keys"),
        api.get<{ webhooks: WebhookSub[] }>("/developer/webhooks"),
        api.get<{ apps: OAuthApp[] }>("/developer/oauth/apps"),
      ]);
      if (keysRes.status === "fulfilled") setApiKeys(keysRes.value.keys || []);
      if (whRes.status === "fulfilled") setWebhooks(whRes.value.webhooks || []);
      if (oaRes.status === "fulfilled") setOAuthApps(oaRes.value.apps || []);
    } catch { /* offline */ }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const createAPIKey = async () => {
    try {
      const res = await api.post<{ key: string; id: string }>("/developer/api-keys", {
        name: newKeyName,
        scopes: ["read", "write", "agents", "campaigns"],
      });
      setNewKeyResult(res.key);
      loadData();
    } catch { /* error */ }
  };

  const revokeKey = async (keyId: string) => {
    try {
      await api.delete(`/developer/api-keys/${keyId}`);
      loadData();
    } catch { /* error */ }
  };

  const createWebhook = async () => {
    if (!newWebhookUrl) return;
    try {
      await api.post("/developer/webhooks", { url: newWebhookUrl, events: ["*"] });
      setNewWebhookUrl("");
      loadData();
    } catch { /* error */ }
  };

  const deleteWebhook = async (id: string) => {
    try { await api.delete(`/developer/webhooks/${id}`); loadData(); } catch { /* */ }
  };

  const createOAuthApp = async () => {
    if (!newAppName || !newAppRedirect) return;
    try {
      const res = await api.post<{ client_id: string; client_secret: string }>("/developer/oauth/apps", {
        name: newAppName,
        redirect_uris: [newAppRedirect],
        scopes: ["profile", "agents"],
      });
      setNewAppResult({ clientId: res.client_id, clientSecret: res.client_secret });
      setNewAppName("");
      setNewAppRedirect("");
      loadData();
    } catch { /* error */ }
  };

  const deleteOAuthApp = async (id: string) => {
    try { await api.delete(`/developer/oauth/apps/${id}`); loadData(); } catch { /* */ }
  };

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
          <span className="font-display font-bold text-surface-900 text-sm">Developer Portal</span>
        </div>
        <div className="flex-1" />
        <button onClick={() => router.push("/marketplace")} className="btn-secondary text-xs">
          Marketplace
        </button>
      </header>

      <div className="flex min-h-[calc(100vh-56px)]">
        {/* Sidebar */}
        <aside className="w-56 border-r border-surface-200 bg-white p-3 space-y-1">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all ${
                tab === t.id
                  ? "bg-brand-50 text-brand-700 font-medium border border-brand-200"
                  : "text-surface-600 hover:bg-surface-50 border border-transparent"
              }`}
            >
              {t.label}
            </button>
          ))}
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {/* Overview */}
            {tab === "overview" && (
              <div className="space-y-8">
                <div>
                  <h1 className="text-2xl font-display font-bold text-surface-900 mb-2">Developer Platform</h1>
                  <p className="text-surface-500">Build integrations, publish agents, and extend Omni OS.</p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="card p-5">
                    <h3 className="font-medium text-surface-900 mb-1">API Keys</h3>
                    <p className="text-xs text-surface-500 mb-3">Authenticate your apps with the Omni API.</p>
                    <div className="text-2xl font-bold text-brand-600">{apiKeys.filter(k => !k.revoked).length}</div>
                    <p className="text-2xs text-surface-400">active keys</p>
                  </div>
                  <div className="card p-5">
                    <h3 className="font-medium text-surface-900 mb-1">Webhooks</h3>
                    <p className="text-xs text-surface-500 mb-3">Receive events when things happen in Omni.</p>
                    <div className="text-2xl font-bold text-brand-600">{webhooks.filter(w => w.active).length}</div>
                    <p className="text-2xs text-surface-400">active subscriptions</p>
                  </div>
                  <div className="card p-5">
                    <h3 className="font-medium text-surface-900 mb-1">OAuth Apps</h3>
                    <p className="text-xs text-surface-500 mb-3">&quot;Sign in with Omni&quot; for your apps.</p>
                    <div className="text-2xl font-bold text-brand-600">{oauthApps.length}</div>
                    <p className="text-2xs text-surface-400">registered apps</p>
                  </div>
                </div>

                <div className="card p-5">
                  <h3 className="font-medium text-surface-900 mb-2">Quick Links</h3>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <a href="/docs" className="text-brand-600 hover:underline">API Documentation (OpenAPI)</a>
                    <a href="/redoc" className="text-brand-600 hover:underline">API Reference (ReDoc)</a>
                    <button onClick={() => setTab("protocol")} className="text-brand-600 hover:underline text-left">Agent Protocol Spec</button>
                    <button onClick={() => router.push("/marketplace")} className="text-brand-600 hover:underline text-left">Agent Marketplace</button>
                  </div>
                </div>

                <div className="card p-5 bg-surface-900 text-white">
                  <h3 className="font-medium mb-2">SDK Install</h3>
                  <div className="space-y-2 text-sm font-mono">
                    <div className="bg-black/30 rounded-lg p-3">
                      <span className="text-surface-400"># npm</span><br />
                      npm install @omnios/sdk
                    </div>
                    <div className="bg-black/30 rounded-lg p-3">
                      <span className="text-surface-400"># pip</span><br />
                      pip install omnios
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* API Keys */}
            {tab === "api-keys" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-surface-900 mb-1">API Keys</h2>
                  <p className="text-sm text-surface-500">
                    Create API keys to authenticate with the Omni OS REST API from your applications.
                  </p>
                </div>

                {/* Create Key */}
                <div className="card p-4 space-y-3">
                  <h3 className="text-sm font-medium text-surface-700">Create New Key</h3>
                  <div className="flex gap-3">
                    <input
                      className="input-field flex-1"
                      placeholder="Key name"
                      value={newKeyName}
                      onChange={e => setNewKeyName(e.target.value)}
                    />
                    <button onClick={createAPIKey} className="btn-primary text-sm">Create Key</button>
                  </div>
                  {newKeyResult && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3">
                      <p className="text-xs text-emerald-700 font-medium mb-1">Key created — save it now!</p>
                      <code className="text-xs text-emerald-800 break-all select-all">{newKeyResult}</code>
                      <button onClick={() => setNewKeyResult(null)} className="block text-xs text-emerald-600 mt-2 underline">Dismiss</button>
                    </div>
                  )}
                </div>

                {/* Key List */}
                <div className="space-y-2">
                  {apiKeys.length === 0 ? (
                    <div className="text-center py-12 text-surface-400 text-sm">No API keys yet.</div>
                  ) : apiKeys.map(k => (
                    <div key={k.id} className={`card px-4 py-3 flex items-center gap-3 ${k.revoked ? "opacity-40" : ""}`}>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-surface-800">{k.name}</div>
                        <div className="text-xs text-surface-400 font-mono">{k.prefix}...</div>
                      </div>
                      <div className="flex gap-1">
                        {k.scopes.map(s => (
                          <span key={s} className="badge text-2xs bg-surface-100 text-surface-500">{s}</span>
                        ))}
                      </div>
                      {k.last_used_at && (
                        <span className="text-2xs text-surface-400">
                          Used {new Date(k.last_used_at).toLocaleDateString()}
                        </span>
                      )}
                      {k.revoked ? (
                        <span className="badge text-2xs bg-red-100 text-red-600">Revoked</span>
                      ) : (
                        <button onClick={() => revokeKey(k.id)} className="btn-ghost text-xs text-red-500">Revoke</button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Webhooks */}
            {tab === "webhooks" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-surface-900 mb-1">Outbound Webhooks</h2>
                  <p className="text-sm text-surface-500">
                    Receive real-time notifications when agents complete, leads are created, emails are sent, and more.
                  </p>
                </div>

                <div className="card p-4 space-y-3">
                  <h3 className="text-sm font-medium text-surface-700">Add Webhook</h3>
                  <div className="flex gap-3">
                    <input
                      className="input-field flex-1"
                      placeholder="https://your-app.com/webhooks/omni"
                      value={newWebhookUrl}
                      onChange={e => setNewWebhookUrl(e.target.value)}
                    />
                    <button onClick={createWebhook} className="btn-primary text-sm" disabled={!newWebhookUrl}>Add</button>
                  </div>
                </div>

                <div className="space-y-2">
                  {webhooks.length === 0 ? (
                    <div className="text-center py-12 text-surface-400 text-sm">No webhooks configured.</div>
                  ) : webhooks.map(w => (
                    <div key={w.id} className="card px-4 py-3 flex items-center gap-3">
                      <div className={`w-2 h-2 rounded-full ${w.active ? "bg-emerald-500" : "bg-surface-300"}`} />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-surface-800 truncate font-mono">{w.url}</div>
                        <div className="text-xs text-surface-400">
                          {w.events.join(", ")}
                          {w.failure_count > 0 && <span className="text-red-500 ml-2">{w.failure_count} failures</span>}
                        </div>
                      </div>
                      {w.last_status_code > 0 && (
                        <span className={`badge text-2xs ${w.last_status_code < 300 ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}>
                          {w.last_status_code}
                        </span>
                      )}
                      <button onClick={() => deleteWebhook(w.id)} className="btn-ghost text-xs text-red-500">Delete</button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* OAuth Apps */}
            {tab === "oauth" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-surface-900 mb-1">OAuth Applications</h2>
                  <p className="text-sm text-surface-500">
                    Register apps to enable &quot;Sign in with Omni&quot; and access user data with their permission.
                  </p>
                </div>

                <div className="card p-4 space-y-3">
                  <h3 className="text-sm font-medium text-surface-700">Register App</h3>
                  <div className="space-y-3">
                    <input
                      className="input-field"
                      placeholder="App name"
                      value={newAppName}
                      onChange={e => setNewAppName(e.target.value)}
                    />
                    <input
                      className="input-field"
                      placeholder="Redirect URI (e.g., https://your-app.com/callback)"
                      value={newAppRedirect}
                      onChange={e => setNewAppRedirect(e.target.value)}
                    />
                    <button onClick={createOAuthApp} className="btn-primary text-sm" disabled={!newAppName || !newAppRedirect}>
                      Register App
                    </button>
                  </div>
                  {newAppResult && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 space-y-1">
                      <p className="text-xs text-emerald-700 font-medium">App registered — save these credentials!</p>
                      <p className="text-xs"><strong>Client ID:</strong> <code className="select-all">{newAppResult.clientId}</code></p>
                      <p className="text-xs"><strong>Client Secret:</strong> <code className="select-all">{newAppResult.clientSecret}</code></p>
                      <button onClick={() => setNewAppResult(null)} className="text-xs text-emerald-600 underline">Dismiss</button>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  {oauthApps.length === 0 ? (
                    <div className="text-center py-12 text-surface-400 text-sm">No OAuth apps registered.</div>
                  ) : oauthApps.map(app => (
                    <div key={app.id} className="card px-4 py-3 flex items-center gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-surface-800">{app.name}</div>
                        <div className="text-xs text-surface-400 font-mono">{app.client_id}</div>
                      </div>
                      <div className="flex gap-1">
                        {app.scopes.map(s => (
                          <span key={s} className="badge text-2xs bg-surface-100 text-surface-500">{s}</span>
                        ))}
                      </div>
                      <button onClick={() => deleteOAuthApp(app.id)} className="btn-ghost text-xs text-red-500">Delete</button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Agent Protocol */}
            {tab === "protocol" && (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-semibold text-surface-900 mb-1">Omni Agent Protocol (OAP)</h2>
                  <p className="text-sm text-surface-500">
                    An open standard for building agents that integrate with Omni OS. Any agent that implements
                    the OAP can be registered, discovered, and executed on the platform.
                  </p>
                </div>

                <div className="card p-5 space-y-4">
                  <h3 className="font-medium text-surface-900">How It Works</h3>
                  <div className="space-y-3 text-sm text-surface-600">
                    <div className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">1</div>
                      <div><strong>Define a manifest</strong> — Describe your agent&apos;s capabilities, inputs, outputs, and endpoint.</div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">2</div>
                      <div><strong>Register with Omni</strong> — <code className="text-xs bg-surface-100 px-1 rounded">POST /protocol/agents/register</code></div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">3</div>
                      <div><strong>Receive execution requests</strong> — Omni sends <code className="text-xs bg-surface-100 px-1 rounded">AgentExecutionRequest</code> to your endpoint.</div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">4</div>
                      <div><strong>Return results</strong> — POST <code className="text-xs bg-surface-100 px-1 rounded">AgentExecutionResult</code> to the callback URL or stream via SSE.</div>
                    </div>
                    <div className="flex gap-3">
                      <div className="w-6 h-6 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center text-xs font-bold shrink-0">5</div>
                      <div><strong>Publish to marketplace</strong> — Submit for review and earn revenue from installs.</div>
                    </div>
                  </div>
                </div>

                <div className="card p-5">
                  <h3 className="font-medium text-surface-900 mb-3">Example Manifest</h3>
                  <pre className="bg-surface-900 text-surface-100 rounded-lg p-4 text-xs overflow-x-auto">{`{
  "name": "SEO Analyzer",
  "version": "1.0.0",
  "description": "Analyzes websites for SEO issues",
  "author": "your-name",
  "category": "marketing",
  "tags": ["seo", "analysis", "audit"],
  "capabilities": [{
    "id": "seo_audit",
    "name": "Full SEO Audit",
    "input_schema": { "url": "string" },
    "output_schema": { "score": "number", "issues": "array" }
  }],
  "endpoint": "https://your-api.com/agents/seo",
  "auth_type": "api_key",
  "streaming": true,
  "pricing_model": "per_run",
  "cost_per_run": 0.50
}`}</pre>
                </div>

                <div className="card p-5">
                  <h3 className="font-medium text-surface-900 mb-3">Protocol Endpoints</h3>
                  <div className="space-y-2 text-sm font-mono">
                    <div className="flex gap-3 items-center">
                      <span className="badge text-2xs bg-blue-100 text-blue-700 w-12 text-center">GET</span>
                      <span className="text-surface-700">/protocol/spec</span>
                      <span className="text-surface-400 text-xs font-sans">Full protocol specification</span>
                    </div>
                    <div className="flex gap-3 items-center">
                      <span className="badge text-2xs bg-emerald-100 text-emerald-700 w-12 text-center">POST</span>
                      <span className="text-surface-700">/protocol/agents/register</span>
                      <span className="text-surface-400 text-xs font-sans">Register an agent</span>
                    </div>
                    <div className="flex gap-3 items-center">
                      <span className="badge text-2xs bg-blue-100 text-blue-700 w-12 text-center">GET</span>
                      <span className="text-surface-700">/protocol/agents</span>
                      <span className="text-surface-400 text-xs font-sans">List registered agents</span>
                    </div>
                    <div className="flex gap-3 items-center">
                      <span className="badge text-2xs bg-emerald-100 text-emerald-700 w-12 text-center">POST</span>
                      <span className="text-surface-700">/protocol/execute</span>
                      <span className="text-surface-400 text-xs font-sans">Execute an external agent</span>
                    </div>
                    <div className="flex gap-3 items-center">
                      <span className="badge text-2xs bg-emerald-100 text-emerald-700 w-12 text-center">POST</span>
                      <span className="text-surface-700">/protocol/callback</span>
                      <span className="text-surface-400 text-xs font-sans">Receive execution results</span>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

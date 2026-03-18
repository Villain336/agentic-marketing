"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { AGENTS, DEPARTMENTS } from "@/lib/constants";
import type {
  AgentDef, Department, AutonomySettingsResponse,
  AgentAutonomySettings, TriggerRule, ApprovalItemResponse, EventEntry,
} from "@/types";

// ── Constants ────────────────────────────────────────────────────────────

const AUTONOMY_LEVELS = [
  { value: "autonomous", label: "Autonomous", desc: "Agent acts freely — no approval needed", color: "bg-emerald-100 text-emerald-700" },
  { value: "guided", label: "Guided", desc: "Sensitive actions require approval", color: "bg-amber-100 text-amber-700" },
  { value: "human_override", label: "Human Override", desc: "All actions require approval", color: "bg-red-100 text-red-700" },
];

const TABS = [
  { id: "global", label: "Global Settings" },
  { id: "agents", label: "Agent Preferences" },
  { id: "triggers", label: "Event Triggers" },
  { id: "approvals", label: "Approval Queue" },
  { id: "events", label: "Event Log" },
] as const;

type TabId = typeof TABS[number]["id"];

// ── Settings Page ────────────────────────────────────────────────────────

export default function SettingsPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<TabId>("global");
  const [settings, setSettings] = useState<AutonomySettingsResponse | null>(null);
  const [agentSettings, setAgentSettings] = useState<Record<string, AgentAutonomySettings>>({});
  const [triggers, setTriggers] = useState<TriggerRule[]>([]);
  const [approvals, setApprovals] = useState<ApprovalItemResponse[]>([]);
  const [events, setEvents] = useState<EventEntry[]>([]);
  const [saving, setSaving] = useState(false);
  const [selectedDept, setSelectedDept] = useState<Department | "all">("all");
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);

  // Load data
  useEffect(() => {
    loadSettings();
  }, []);

  useEffect(() => {
    if (activeTab === "triggers") loadTriggers();
    if (activeTab === "approvals") loadApprovals();
    if (activeTab === "events") loadEvents();
  }, [activeTab]);

  const loadSettings = async () => {
    try {
      const [s, a] = await Promise.all([
        api.getAutonomySettings(),
        api.getAgentSettings(),
      ]);
      setSettings(s);
      setAgentSettings(a);
    } catch {
      // Backend might be offline — use defaults
      setSettings({
        global_level: "guided",
        spending_approval_threshold: 100,
        outbound_approval_required: true,
        content_approval_required: true,
        infrastructure_approval_required: true,
        escalation_channel: "email",
        per_agent: {},
      });
    }
  };

  const loadTriggers = async () => {
    try { setTriggers(await api.getTriggers()); } catch { /* offline */ }
  };

  const loadApprovals = async () => {
    try { setApprovals(await api.getApprovals()); } catch { /* offline */ }
  };

  const loadEvents = async () => {
    try { setEvents(await api.getEvents("", 100)); } catch { /* offline */ }
  };

  const saveGlobalSettings = useCallback(async (updates: Partial<AutonomySettingsResponse>) => {
    if (!settings) return;
    setSaving(true);
    const updated = { ...settings, ...updates };
    setSettings(updated);
    try {
      await api.updateAutonomySettings(updates);
    } catch { /* offline */ }
    setSaving(false);
  }, [settings]);

  const saveAgentSetting = useCallback(async (agentId: string, updates: Partial<AgentAutonomySettings>) => {
    setSaving(true);
    const current = agentSettings[agentId] || { agent_id: agentId, autonomy_level: "", enabled: true, max_iterations: 0, spending_limit: 0, allowed_tools: [], blocked_tools: [], auto_approve_tools: [], notes: "" };
    const updated = { ...current, ...updates };
    setAgentSettings(prev => ({ ...prev, [agentId]: updated }));
    try {
      await api.updateAgentSettings(agentId, updates);
    } catch { /* offline */ }
    setSaving(false);
  }, [agentSettings]);

  const decideApproval = async (itemId: string, decision: "approved" | "rejected") => {
    try {
      await api.decideApproval(itemId, decision);
      loadApprovals();
    } catch { /* offline */ }
  };

  const toggleTrigger = async (rule: TriggerRule) => {
    try {
      await api.updateTrigger(rule.id, { enabled: !rule.enabled });
      loadTriggers();
    } catch { /* offline */ }
  };

  if (!settings) return null;

  const filteredAgents = selectedDept === "all" ? AGENTS : AGENTS.filter(a => a.department === selectedDept);

  return (
    <div className="h-screen flex flex-col bg-surface-50">
      {/* Header */}
      <header className="h-14 bg-white border-b border-surface-200 flex items-center px-6 gap-4 flex-shrink-0">
        <button onClick={() => router.push("/dashboard")} className="btn-ghost text-xs">
          &#8592; Dashboard
        </button>
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">S</span>
          </div>
          <span className="font-display font-bold text-surface-900 text-sm">Settings</span>
        </div>
        <div className="flex-1" />
        {saving && <span className="text-xs text-surface-400 animate-pulse">Saving...</span>}
      </header>

      <div className="flex-1 flex min-h-0">
        {/* Tab Sidebar */}
        <aside className="w-56 border-r border-surface-200 bg-white flex-shrink-0 p-3 space-y-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full text-left px-3 py-2.5 rounded-lg text-sm transition-all ${
                activeTab === tab.id
                  ? "bg-brand-50 text-brand-700 font-medium border border-brand-200"
                  : "text-surface-600 hover:bg-surface-50 border border-transparent"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </aside>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          <div className="max-w-4xl mx-auto">
            {activeTab === "global" && (
              <GlobalSettingsTab settings={settings} onSave={saveGlobalSettings} />
            )}
            {activeTab === "agents" && (
              <AgentSettingsTab
                agents={filteredAgents}
                agentSettings={agentSettings}
                globalLevel={settings.global_level}
                selectedDept={selectedDept}
                onSelectDept={setSelectedDept}
                expandedAgent={expandedAgent}
                onExpandAgent={setExpandedAgent}
                onSave={saveAgentSetting}
              />
            )}
            {activeTab === "triggers" && (
              <TriggersTab triggers={triggers} onToggle={toggleTrigger} onRefresh={loadTriggers} />
            )}
            {activeTab === "approvals" && (
              <ApprovalsTab approvals={approvals} onDecide={decideApproval} onRefresh={loadApprovals} />
            )}
            {activeTab === "events" && (
              <EventsTab events={events} onRefresh={loadEvents} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB: Global Settings
// ═══════════════════════════════════════════════════════════════════════════════

function GlobalSettingsTab({ settings, onSave }: {
  settings: AutonomySettingsResponse;
  onSave: (updates: Partial<AutonomySettingsResponse>) => void;
}) {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-surface-900 mb-1">Autonomy Level</h2>
        <p className="text-sm text-surface-500 mb-4">Controls how much freedom agents have to act independently.</p>
        <div className="grid grid-cols-3 gap-3">
          {AUTONOMY_LEVELS.map(level => (
            <button
              key={level.value}
              onClick={() => onSave({ global_level: level.value as AutonomySettingsResponse["global_level"] })}
              className={`p-4 rounded-xl border-2 text-left transition-all ${
                settings.global_level === level.value
                  ? "border-brand-500 bg-brand-50 shadow-sm"
                  : "border-surface-200 hover:border-surface-300 bg-white"
              }`}
            >
              <div className={`badge text-xs mb-2 ${level.color}`}>{level.label}</div>
              <p className="text-xs text-surface-500">{level.desc}</p>
            </button>
          ))}
        </div>
      </div>

      <hr className="border-surface-100" />

      <div>
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Approval Gates</h2>
        <div className="space-y-3">
          <ToggleRow
            label="Outbound Communications"
            description="Emails, calls, social posts, messages"
            checked={settings.outbound_approval_required}
            onChange={(v) => onSave({ outbound_approval_required: v })}
          />
          <ToggleRow
            label="Content Publishing"
            description="Blog posts, website deployments, CMS publishes"
            checked={settings.content_approval_required}
            onChange={(v) => onSave({ content_approval_required: v })}
          />
          <ToggleRow
            label="Infrastructure Changes"
            description="DNS, deployments, domain registration, cloud resources"
            checked={settings.infrastructure_approval_required}
            onChange={(v) => onSave({ infrastructure_approval_required: v })}
          />
        </div>
      </div>

      <hr className="border-surface-100" />

      <div>
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Spending</h2>
        <div className="flex items-center gap-4">
          <label className="text-sm text-surface-600 min-w-[200px]">Approval threshold ($)</label>
          <input
            type="number"
            className="input-field w-32"
            value={settings.spending_approval_threshold}
            onChange={(e) => onSave({ spending_approval_threshold: Number(e.target.value) })}
          />
          <span className="text-xs text-surface-400">Actions costing more than this need approval</span>
        </div>
      </div>

      <hr className="border-surface-100" />

      <div>
        <h2 className="text-lg font-semibold text-surface-900 mb-4">Escalation Channel</h2>
        <div className="flex gap-2">
          {["email", "slack", "telegram", "whatsapp"].map(ch => (
            <button
              key={ch}
              onClick={() => onSave({ escalation_channel: ch })}
              className={`badge text-xs capitalize ${
                settings.escalation_channel === ch
                  ? "bg-brand-100 text-brand-700"
                  : "bg-surface-100 text-surface-500 hover:bg-surface-200"
              }`}
            >
              {ch}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB: Agent Preferences
// ═══════════════════════════════════════════════════════════════════════════════

function AgentSettingsTab({ agents, agentSettings, globalLevel, selectedDept, onSelectDept, expandedAgent, onExpandAgent, onSave }: {
  agents: AgentDef[];
  agentSettings: Record<string, AgentAutonomySettings>;
  globalLevel: string;
  selectedDept: Department | "all";
  onSelectDept: (d: Department | "all") => void;
  expandedAgent: string | null;
  onExpandAgent: (id: string | null) => void;
  onSave: (agentId: string, updates: Partial<AgentAutonomySettings>) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-surface-900 mb-1">Agent Preferences</h2>
        <p className="text-sm text-surface-500 mb-4">
          Override autonomy, enable/disable, or configure per-agent settings.
          Agents default to the global level ({globalLevel}) unless overridden.
        </p>
      </div>

      {/* Department Filter */}
      <div className="flex flex-wrap gap-1 mb-4">
        <button
          onClick={() => onSelectDept("all")}
          className={`badge text-2xs transition-all ${
            selectedDept === "all" ? "bg-surface-900 text-white" : "bg-surface-100 text-surface-500 hover:bg-surface-200"
          }`}
        >
          All
        </button>
        {DEPARTMENTS.map(d => (
          <button
            key={d.id}
            onClick={() => onSelectDept(d.id)}
            className={`badge text-2xs transition-all ${
              selectedDept === d.id ? d.color : "bg-surface-100 text-surface-500 hover:bg-surface-200"
            }`}
          >
            {d.label}
          </button>
        ))}
      </div>

      {/* Agent List */}
      <div className="space-y-2">
        {agents.map(agent => {
          const cfg = agentSettings[agent.id];
          const isExpanded = expandedAgent === agent.id;
          const effectiveLevel = cfg?.autonomy_level || globalLevel;
          const isEnabled = cfg?.enabled !== false;
          const levelInfo = AUTONOMY_LEVELS.find(l => l.value === effectiveLevel) || AUTONOMY_LEVELS[1];

          return (
            <div key={agent.id} className="card">
              {/* Agent Row */}
              <div
                className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-surface-50 rounded-xl"
                onClick={() => onExpandAgent(isExpanded ? null : agent.id)}
              >
                <div className={`w-2 h-2 rounded-full ${isEnabled ? "bg-emerald-500" : "bg-surface-300"}`} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-surface-800">{agent.label}</span>
                  <span className="text-xs text-surface-400 ml-2">{agent.role}</span>
                </div>
                <div className={`badge text-2xs ${levelInfo.color}`}>
                  {cfg?.autonomy_level ? levelInfo.label : `${levelInfo.label} (global)`}
                </div>
                <span className="text-surface-300 text-xs">{isExpanded ? "▼" : "▶"}</span>
              </div>

              {/* Expanded Settings */}
              {isExpanded && (
                <div className="px-4 pb-4 pt-1 border-t border-surface-100 space-y-4">
                  {/* Enable/Disable */}
                  <ToggleRow
                    label="Enabled"
                    description="When disabled, this agent will be skipped during campaign execution"
                    checked={isEnabled}
                    onChange={(v) => onSave(agent.id, { enabled: v })}
                  />

                  {/* Autonomy Level Override */}
                  <div>
                    <label className="text-sm text-surface-600 font-medium mb-2 block">Autonomy Level</label>
                    <div className="flex gap-2">
                      <button
                        onClick={() => onSave(agent.id, { autonomy_level: "" })}
                        className={`badge text-xs ${
                          !cfg?.autonomy_level ? "bg-surface-900 text-white" : "bg-surface-100 text-surface-500"
                        }`}
                      >
                        Use Global
                      </button>
                      {AUTONOMY_LEVELS.map(level => (
                        <button
                          key={level.value}
                          onClick={() => onSave(agent.id, { autonomy_level: level.value })}
                          className={`badge text-xs ${
                            cfg?.autonomy_level === level.value ? level.color : "bg-surface-100 text-surface-500"
                          }`}
                        >
                          {level.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Spending Limit */}
                  <div className="flex items-center gap-4">
                    <label className="text-sm text-surface-600 min-w-[140px]">Spending limit ($)</label>
                    <input
                      type="number"
                      className="input-field w-32"
                      placeholder="Use global"
                      value={cfg?.spending_limit || ""}
                      onChange={(e) => onSave(agent.id, { spending_limit: Number(e.target.value) })}
                    />
                  </div>

                  {/* Max Iterations */}
                  <div className="flex items-center gap-4">
                    <label className="text-sm text-surface-600 min-w-[140px]">Max iterations</label>
                    <input
                      type="number"
                      className="input-field w-32"
                      placeholder="Default (15)"
                      value={cfg?.max_iterations || ""}
                      onChange={(e) => onSave(agent.id, { max_iterations: Number(e.target.value) })}
                    />
                  </div>

                  {/* Notes */}
                  <div>
                    <label className="text-sm text-surface-600 font-medium mb-1 block">Notes</label>
                    <textarea
                      className="input-field resize-none"
                      rows={2}
                      placeholder="Add notes about this agent's configuration..."
                      value={cfg?.notes || ""}
                      onChange={(e) => onSave(agent.id, { notes: e.target.value })}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB: Event Triggers
// ═══════════════════════════════════════════════════════════════════════════════

function TriggersTab({ triggers, onToggle, onRefresh }: {
  triggers: TriggerRule[];
  onToggle: (rule: TriggerRule) => void;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-surface-900 mb-1">Event Triggers</h2>
          <p className="text-sm text-surface-500">
            Rules that automatically trigger agents when events occur. These define cross-agent pipelines.
          </p>
        </div>
        <button onClick={onRefresh} className="btn-secondary text-xs">Refresh</button>
      </div>

      <div className="space-y-2">
        {triggers.length === 0 && (
          <div className="text-center py-12 text-surface-400 text-sm">
            No triggers configured. Start the backend to load defaults.
          </div>
        )}
        {triggers.map(rule => (
          <div key={rule.id} className={`card px-4 py-3 flex items-center gap-3 ${!rule.enabled ? "opacity-50" : ""}`}>
            <button
              onClick={() => onToggle(rule)}
              className={`w-10 h-5 rounded-full flex items-center transition-all ${
                rule.enabled ? "bg-emerald-500 justify-end" : "bg-surface-300 justify-start"
              }`}
            >
              <div className="w-4 h-4 rounded-full bg-white shadow-sm mx-0.5" />
            </button>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-surface-800">{rule.name || rule.id}</div>
              <div className="text-xs text-surface-400">
                {rule.event_type}
                {rule.source_agent ? ` from ${rule.source_agent}` : ""}
                {" → "}
                <span className="text-brand-600">{rule.action}</span>
                {rule.target_agent ? ` (${rule.target_agent})` : ""}
              </div>
            </div>
            <div className="badge text-2xs bg-surface-100 text-surface-500">
              {rule.cooldown_seconds}s cooldown
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB: Approval Queue
// ═══════════════════════════════════════════════════════════════════════════════

function ApprovalsTab({ approvals, onDecide, onRefresh }: {
  approvals: ApprovalItemResponse[];
  onDecide: (id: string, decision: "approved" | "rejected") => void;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-surface-900 mb-1">Approval Queue</h2>
          <p className="text-sm text-surface-500">
            Actions awaiting your approval. Approve or reject agent requests.
          </p>
        </div>
        <button onClick={onRefresh} className="btn-secondary text-xs">Refresh</button>
      </div>

      {approvals.length === 0 ? (
        <div className="text-center py-12 text-surface-400 text-sm">
          No pending approvals. Agents are operating within their autonomy limits.
        </div>
      ) : (
        <div className="space-y-2">
          {approvals.map(item => (
            <div key={item.id} className="card px-4 py-3 space-y-2">
              <div className="flex items-center gap-3">
                <div className="badge text-2xs bg-amber-100 text-amber-700">{item.action_type}</div>
                <span className="text-sm font-medium text-surface-800">
                  {AGENTS.find(a => a.id === item.agent_id)?.label || item.agent_id}
                </span>
                <span className="text-xs text-surface-400">
                  {new Date(item.created_at).toLocaleString()}
                </span>
              </div>
              <div className="text-xs text-surface-500 bg-surface-50 rounded-lg p-2 font-mono">
                {JSON.stringify(item.content, null, 2).slice(0, 300)}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => onDecide(item.id, "approved")}
                  className="btn-primary text-xs py-1.5"
                >
                  Approve
                </button>
                <button
                  onClick={() => onDecide(item.id, "rejected")}
                  className="btn-secondary text-xs py-1.5"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// TAB: Event Log
// ═══════════════════════════════════════════════════════════════════════════════

function EventsTab({ events, onRefresh }: {
  events: EventEntry[];
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-surface-900 mb-1">Event Log</h2>
          <p className="text-sm text-surface-500">
            Recent events from the event bus. Shows agent lifecycle, tool executions, and trigger firings.
          </p>
        </div>
        <button onClick={onRefresh} className="btn-secondary text-xs">Refresh</button>
      </div>

      {events.length === 0 ? (
        <div className="text-center py-12 text-surface-400 text-sm">
          No events yet. Events will appear as agents run.
        </div>
      ) : (
        <div className="space-y-1">
          {events.slice().reverse().map(event => (
            <div key={event.id} className="flex items-start gap-3 px-3 py-2 hover:bg-surface-50 rounded-lg text-xs">
              <EventDot type={event.type} />
              <div className="flex-1 min-w-0">
                <span className="font-medium text-surface-700">{event.type}</span>
                {event.source_agent && (
                  <span className="text-surface-400 ml-2">from {event.source_agent}</span>
                )}
                {Object.keys(event.data).length > 0 && (
                  <span className="text-surface-300 ml-2 truncate">
                    {JSON.stringify(event.data).slice(0, 80)}
                  </span>
                )}
              </div>
              <span className="text-surface-300 text-2xs flex-shrink-0">
                {new Date(event.timestamp).toLocaleTimeString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// SHARED COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

function ToggleRow({ label, description, checked, onChange }: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <div>
        <div className="text-sm font-medium text-surface-700">{label}</div>
        <div className="text-xs text-surface-400">{description}</div>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full flex items-center transition-all flex-shrink-0 ${
          checked ? "bg-brand-500 justify-end" : "bg-surface-300 justify-start"
        }`}
      >
        <div className="w-4 h-4 rounded-full bg-white shadow-sm mx-0.5" />
      </button>
    </div>
  );
}

function EventDot({ type }: { type: string }) {
  let color = "bg-surface-300";
  if (type.includes("completed")) color = "bg-emerald-500";
  else if (type.includes("started")) color = "bg-blue-500";
  else if (type.includes("failed") || type.includes("error")) color = "bg-red-500";
  else if (type.includes("approval")) color = "bg-amber-500";
  else if (type.includes("tool")) color = "bg-violet-500";
  return <div className={`w-2 h-2 rounded-full mt-1 flex-shrink-0 ${color}`} />;
}

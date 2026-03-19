"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { DEPARTMENTS, AGENTS, getAgentsByDepartment } from "@/lib/constants";
import type { AgentDef, AgentRun, AgentStatus, Grade, SSEEvent, BusinessProfile, Department } from "@/types";

// ── Grade Colors ────────────────────────────────────────────────────────

const GRADE_COLORS: Record<string, string> = {
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

const STATUS_COLORS: Record<AgentStatus, string> = {
  idle: "bg-surface-200",
  queued: "bg-amber-300",
  running: "bg-brand-500 animate-pulse",
  done: "bg-emerald-500",
  error: "bg-red-500",
};

// ── Dashboard Page ──────────────────────────────────────────────────────

export default function DashboardPage() {
  const router = useRouter();
  const [business, setBusiness] = useState<BusinessProfile | null>(null);
  const [agentRuns, setAgentRuns] = useState<Record<string, AgentRun>>({});
  const [selectedAgent, setSelectedAgent] = useState<string>("prospector");
  const [selectedDept, setSelectedDept] = useState<Department | "all">("all");
  const [running, setRunning] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"checking" | "online" | "offline">("checking");
  const [memory, setMemory] = useState<Record<string, unknown>>({});
  const [campaignId, setCampaignId] = useState<string>("");
  const [showSidebar, setShowSidebar] = useState(true);
  const [scores, setScores] = useState<Record<string, { score: number; grade: string }>>({});
  const controllerRef = useRef<AbortController | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  // Load session
  useEffect(() => {
    const savedBiz = localStorage.getItem("sv_business");
    if (savedBiz) {
      setBusiness(JSON.parse(savedBiz));
    } else {
      router.push("/onboarding");
      return;
    }
    // Check backend
    api.health().then((h) => setBackendStatus(h.status === "offline" ? "offline" : "online"));
  }, [router]);

  // Auto-scroll output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [agentRuns, selectedAgent]);

  const updateAgentRun = useCallback((agentId: string, update: Partial<AgentRun>) => {
    setAgentRuns((prev) => ({
      ...prev,
      [agentId]: { ...prev[agentId], ...update } as AgentRun,
    }));
  }, []);

  // Fetch real scores from backend after agents complete
  const refreshScores = useCallback(async (cid: string) => {
    if (!cid) return;
    try {
      const s = await api.getCampaignScores(cid);
      setScores(s);
      // Apply real grades to agent runs
      setAgentRuns((prev) => {
        const updated = { ...prev };
        for (const [agentId, scoreData] of Object.entries(s)) {
          if (updated[agentId]) {
            updated[agentId] = { ...updated[agentId], grade: (scoreData.grade || "—") as Grade, score: scoreData.score || 0 };
          }
        }
        return updated;
      });
    } catch { /* backend offline */ }
  }, []);

  // ── Run single agent ──

  const runAgent = useCallback(
    async (agentId: string) => {
      if (!business || running) return;

      setRunning(true);
      setSelectedAgent(agentId);
      updateAgentRun(agentId, {
        agentId,
        status: "running",
        output: "",
        grade: "—",
        score: 0,
        phases: ["Starting..."],
      });

      const controller = api.streamAgent(
        agentId,
        business,
        memory,
        campaignId,
        (evt: SSEEvent) => {
          if (evt.event === "output" && evt.content) {
            updateAgentRun(agentId, {
              output: evt.content,
              status: "done",
              grade: (scores[agentId]?.grade as Grade) || "—",
              provider: evt.provider,
              model: evt.model,
            });
            if (evt.memory_update) {
              setMemory((prev) => ({ ...prev, ...evt.memory_update }));
            }
            // Fetch real scores from backend
            refreshScores(campaignId);
          } else if (evt.event === "think" && evt.content) {
            setAgentRuns((prev) => {
              const existing = prev[agentId] || { output: "" };
              return {
                ...prev,
                [agentId]: {
                  ...existing,
                  agentId,
                  status: "running" as AgentStatus,
                  phases: [...(existing.phases || []), evt.content || ""],
                } as AgentRun,
              };
            });
          } else if (evt.event === "tool_call") {
            setAgentRuns((prev) => {
              const existing = prev[agentId] || {};
              return {
                ...prev,
                [agentId]: {
                  ...existing,
                  agentId,
                  status: "running" as AgentStatus,
                  phases: [...(existing.phases || []), `Tool: ${evt.tool_name}`],
                } as AgentRun,
              };
            });
          } else if (evt.event === "error") {
            updateAgentRun(agentId, { status: "error", output: evt.content || "Agent failed" });
          }
        },
        () => setRunning(false),
        (err) => {
          updateAgentRun(agentId, { status: "error", output: `Error: ${err}` });
          setRunning(false);
        }
      );
      controllerRef.current = controller;
    },
    [business, memory, campaignId, running, updateAgentRun]
  );

  // ── Run full campaign ──

  const runCampaign = useCallback(async () => {
    if (!business) return;
    const agentOrder = AGENTS.map((a) => a.id);
    const cid = `camp_${Date.now()}`;
    setCampaignId(cid);

    for (const agentId of agentOrder) {
      updateAgentRun(agentId, { agentId, status: "queued", output: "", grade: "—", score: 0, phases: [] });
    }

    for (const agentId of agentOrder) {
      await new Promise<void>((resolve) => {
        setRunning(true);
        setSelectedAgent(agentId);
        updateAgentRun(agentId, { status: "running", phases: ["Starting..."] });

        api.streamAgent(
          agentId,
          business,
          memory,
          cid,
          (evt: SSEEvent) => {
            if (evt.event === "output" && evt.content) {
              updateAgentRun(agentId, {
                output: evt.content,
                status: "done",
                grade: "—" as Grade,
                provider: evt.provider,
              });
              if (evt.memory_update) {
                setMemory((prev) => ({ ...prev, ...evt.memory_update }));
              }
            } else if (evt.event === "think" && evt.content) {
              setAgentRuns((prev) => ({
                ...prev,
                [agentId]: { ...prev[agentId], phases: [...(prev[agentId]?.phases || []), evt.content || ""] } as AgentRun,
              }));
            } else if (evt.event === "error") {
              updateAgentRun(agentId, { status: "error", output: evt.content || "Failed" });
            }
          },
          () => { setRunning(false); refreshScores(cid); resolve(); },
          () => { setRunning(false); resolve(); }
        );
      });
    }
  }, [business, memory, updateAgentRun]);

  const stopAgent = useCallback(() => {
    controllerRef.current?.abort();
    setRunning(false);
  }, []);

  const filteredAgents =
    selectedDept === "all" ? AGENTS : AGENTS.filter((a) => a.department === selectedDept);

  const doneCount = Object.values(agentRuns).filter((r) => r.status === "done").length;
  const currentRun = agentRuns[selectedAgent];

  if (!business) return null;

  return (
    <div className="h-screen flex flex-col bg-surface-50" role="application" aria-label="Supervisor Dashboard">
      {/* ── Top Bar ── */}
      <header className="h-14 bg-white border-b border-surface-200 flex items-center px-4 gap-4 flex-shrink-0" role="banner">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-brand-600 flex items-center justify-center">
            <span className="text-white text-xs font-bold">S</span>
          </div>
          <span className="font-display font-bold text-surface-900 text-sm">{business.name}</span>
        </div>

        <div className="flex-1" />

        <div className="flex items-center gap-3 text-xs">
          <div className={`flex items-center gap-1.5 ${backendStatus === "online" ? "text-emerald-600" : "text-surface-400"}`}>
            <div className={`w-2 h-2 rounded-full ${backendStatus === "online" ? "bg-emerald-500" : "bg-surface-300"}`} />
            {backendStatus === "online" ? "Connected" : "Offline"}
          </div>
          <span className="text-surface-300">|</span>
          <span className="text-surface-500">{doneCount}/{AGENTS.length} agents complete</span>
          <button
            onClick={() => router.push("/settings")}
            className="btn-ghost text-xs text-surface-500"
          >
            Settings
          </button>
          <button
            onClick={() => { localStorage.clear(); router.push("/"); }}
            className="btn-ghost text-xs text-surface-400"
          >
            Logout
          </button>
        </div>
      </header>

      {/* ── Main Layout ── */}
      <div className="flex-1 flex min-h-0">
        {/* ── Left: Agent Sidebar ── */}
        {showSidebar && (
          <aside className="w-72 border-r border-surface-200 bg-white flex flex-col flex-shrink-0" role="navigation" aria-label="Agent list">
            {/* Department Tabs */}
            <div className="p-3 border-b border-surface-100">
              <div className="flex flex-wrap gap-1">
                <button
                  onClick={() => setSelectedDept("all")}
                  className={`badge text-2xs transition-all ${
                    selectedDept === "all" ? "bg-surface-900 text-white" : "bg-surface-100 text-surface-500 hover:bg-surface-200"
                  }`}
                >
                  All
                </button>
                {DEPARTMENTS.map((d) => (
                  <button
                    key={d.id}
                    onClick={() => setSelectedDept(d.id)}
                    className={`badge text-2xs transition-all ${
                      selectedDept === d.id ? d.color : "bg-surface-100 text-surface-500 hover:bg-surface-200"
                    }`}
                  >
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Agent List */}
            <div className="flex-1 overflow-y-auto p-2 space-y-0.5" role="listbox" aria-label="Agents">
              {filteredAgents.map((agent) => {
                const run = agentRuns[agent.id];
                const isSelected = selectedAgent === agent.id;
                return (
                  <button
                    key={agent.id}
                    onClick={() => setSelectedAgent(agent.id)}
                    role="option"
                    aria-selected={isSelected}
                    aria-label={`${agent.label} — ${agent.role}${run?.status ? `, status: ${run.status}` : ""}${run?.grade && run.grade !== "—" ? `, grade: ${run.grade}` : ""}`}
                    className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-3 transition-all group ${
                      isSelected
                        ? "bg-brand-50 border border-brand-200"
                        : "hover:bg-surface-50 border border-transparent"
                    }`}
                  >
                    {/* Status dot */}
                    <div className={`w-2 h-2 rounded-full flex-shrink-0 ${STATUS_COLORS[run?.status || "idle"]}`} />

                    {/* Agent info */}
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-surface-800 truncate">{agent.label}</div>
                      <div className="text-2xs text-surface-400 truncate">{agent.role}</div>
                    </div>

                    {/* Grade */}
                    {run?.grade && run.grade !== "—" && (
                      <div className={`grade-chip text-2xs ${GRADE_COLORS[run.grade]}`}>{run.grade}</div>
                    )}

                    {/* Run button */}
                    <button
                      onClick={(e) => { e.stopPropagation(); runAgent(agent.id); }}
                      className="opacity-0 group-hover:opacity-100 focus:opacity-100 btn-ghost text-2xs px-2 py-1 text-brand-600"
                      disabled={running}
                      aria-label={`Run ${agent.label}`}
                    >
                      Run
                    </button>
                  </button>
                );
              })}
            </div>

            {/* Campaign Controls */}
            <div className="p-3 border-t border-surface-100 space-y-2">
              {running ? (
                <button onClick={stopAgent} className="btn-secondary w-full text-sm" aria-label="Stop running agent">
                  Stop
                </button>
              ) : (
                <button onClick={runCampaign} className="btn-primary w-full text-sm" aria-label="Run all agents in sequence">
                  Run Full Campaign
                </button>
              )}
            </div>
          </aside>
        )}

        {/* ── Center: Agent Output ── */}
        <main className="flex-1 flex flex-col min-w-0" role="main" aria-label="Agent output">
          {/* Agent Header */}
          <div className="h-12 bg-white border-b border-surface-200 flex items-center px-5 gap-3 flex-shrink-0">
            <button onClick={() => setShowSidebar(!showSidebar)} className="btn-ghost text-xs p-1">
              {showSidebar ? "◀" : "▶"}
            </button>
            <div className="flex items-center gap-3 flex-1">
              <div className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[currentRun?.status || "idle"]}`} />
              <span className="font-medium text-sm text-surface-900">
                {AGENTS.find((a) => a.id === selectedAgent)?.label || selectedAgent}
              </span>
              <span className="text-xs text-surface-400">
                {AGENTS.find((a) => a.id === selectedAgent)?.role}
              </span>
            </div>
            {currentRun?.grade && currentRun.grade !== "—" && (
              <div className={`grade-chip ${GRADE_COLORS[currentRun.grade]}`}>{currentRun.grade}</div>
            )}
            {currentRun?.provider && (
              <span className="text-2xs text-surface-400 font-mono">{currentRun.provider}</span>
            )}
          </div>

          {/* Output Area */}
          <div ref={outputRef} className="flex-1 overflow-y-auto">
            {currentRun?.output ? (
              <div className="p-6 max-w-4xl">
                <div className="agent-output" dangerouslySetInnerHTML={{ __html: renderMarkdown(currentRun.output) }} />
              </div>
            ) : currentRun?.status === "running" ? (
              <div className="p-6">
                <div className="space-y-2">
                  {(currentRun.phases || []).slice(-8).map((phase, i) => (
                    <div key={i} className="flex items-center gap-2 text-sm text-surface-500 animate-fade-in">
                      <div className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
                      {phase}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center h-full">
                <div className="text-center py-20">
                  <div className="text-4xl mb-4 opacity-20">&#9881;</div>
                  <p className="text-surface-400 text-sm">
                    Select an agent and click <strong>Run</strong> to see output
                  </p>
                  <p className="text-surface-300 text-xs mt-1">
                    or click <strong>Run Full Campaign</strong> to execute all agents
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Activity Phases Footer */}
          {currentRun?.status === "running" && (
            <div className="h-8 bg-white border-t border-surface-100 flex items-center px-5">
              <div className="flex items-center gap-2 text-xs text-surface-400">
                <div className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
                {currentRun.phases?.[currentRun.phases.length - 1] || "Processing..."}
              </div>
            </div>
          )}
        </main>

        {/* ── Right: Context Panel ── */}
        <aside className="w-64 border-l border-surface-200 bg-white flex-shrink-0 hidden xl:flex flex-col">
          <div className="p-4 border-b border-surface-100">
            <h3 className="text-xs font-semibold text-surface-500 uppercase tracking-wider">Campaign Context</h3>
          </div>
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <ContextBlock label="Business" value={business.name} />
            <ContextBlock label="Service" value={business.service} />
            <ContextBlock label="ICP" value={business.icp} />
            <ContextBlock label="Geography" value={business.geography} />
            <ContextBlock label="Goal" value={business.goal} />
            <ContextBlock label="Entity" value={business.entityType} />
            <hr className="border-surface-100" />
            <div>
              <h4 className="text-xs font-semibold text-surface-500 uppercase tracking-wider mb-2">Agent Scores</h4>
              <div className="space-y-1">
                {Object.entries(agentRuns)
                  .filter(([, r]) => r.grade && r.grade !== "—")
                  .map(([id, r]) => (
                    <div key={id} className="flex items-center justify-between text-xs">
                      <span className="text-surface-600">{AGENTS.find((a) => a.id === id)?.label || id}</span>
                      <span className={`badge text-2xs ${GRADE_COLORS[r.grade]}`}>{r.grade}</span>
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}

// ── Helpers ──────────────────────────────────────────────────────────────

function ContextBlock({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-2xs font-medium text-surface-400 uppercase">{label}</div>
      <div className="text-sm text-surface-700 mt-0.5">{value}</div>
    </div>
  );
}

/** Allowlisted HTML tags for sanitization. */
const ALLOWED_TAGS = new Set(["h2", "h3", "strong", "li", "ul", "hr", "code", "p"]);

/** Strip any HTML tag not in the allowlist (prevents XSS from agent output). */
function sanitizeHtml(html: string): string {
  return html.replace(/<\/?([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>/g, (match, tag) => {
    const lower = tag.toLowerCase();
    if (ALLOWED_TAGS.has(lower)) {
      // Only allow the bare tag — strip attributes
      if (match.startsWith("</")) return `</${lower}>`;
      if (lower === "hr") return "<hr />";
      return `<${lower}>`;
    }
    return ""; // strip disallowed tags
  });
}

function renderMarkdown(text: string): string {
  // First escape any raw HTML in the input
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Then apply markdown transforms (these produce only allowlisted tags)
  const html = escaped
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
    .replace(/^---$/gm, '<hr />')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hulo])/gm, (m) => m ? `<p>${m}` : '')
    .replace(/<p><\/p>/g, '');

  return sanitizeHtml(html);
}

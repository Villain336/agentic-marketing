"use client";

import { useMemo } from "react";
import { AGENTS, DEPARTMENTS } from "@/lib/constants";
import type { AgentDef, AgentRun, AgentStatus, Department } from "@/types";

// ── Layer definitions (execution order) ──────────────────────────────────

const LAYER_ORDER: { label: string; departments: Department[] }[] = [
  { label: "Intelligence", departments: ["intelligence"] },
  { label: "Core Campaign", departments: ["marketing"] },
  { label: "Sales & Revenue", departments: ["sales"] },
  { label: "Operations", departments: ["operations"] },
  { label: "Back Office", departments: ["finance", "legal"] },
  { label: "Engineering", departments: ["engineering"] },
];

const STATUS_FILL: Record<AgentStatus | "idle", string> = {
  idle: "#a1a1aa",
  queued: "#fbbf24",
  running: "#6c5ce7",
  done: "#22c55e",
  error: "#ef4444",
};

const NODE_W = 160;
const NODE_H = 56;
const H_GAP = 32;
const V_GAP = 72;
const LAYER_LABEL_H = 28;
const PAD_X = 24;
const PAD_Y = 20;

// ── Component ────────────────────────────────────────────────────────────

interface Props {
  agentRuns: Record<string, Partial<AgentRun>>;
  onSelectAgent: (id: string) => void;
  selectedAgent: string;
}

interface NodePos {
  agent: AgentDef;
  x: number;
  y: number;
  layerIdx: number;
}

export function AgentPipelineGraph({ agentRuns, onSelectAgent, selectedAgent }: Props) {
  const { nodes, edges, width, height } = useMemo(() => {
    const positioned: NodePos[] = [];
    let curY = PAD_Y;

    const layerStartIndices: number[] = [];

    for (let li = 0; li < LAYER_ORDER.length; li++) {
      const layer = LAYER_ORDER[li];
      const layerAgents = AGENTS.filter((a) => layer.departments.includes(a.department));
      if (layerAgents.length === 0) continue;

      curY += LAYER_LABEL_H;
      layerStartIndices.push(positioned.length);

      const totalW = layerAgents.length * NODE_W + (layerAgents.length - 1) * H_GAP;
      const startX = PAD_X + (layerAgents.length > 1 ? 0 : 0);

      layerAgents.forEach((agent, i) => {
        positioned.push({
          agent,
          x: PAD_X + i * (NODE_W + H_GAP),
          y: curY,
          layerIdx: li,
        });
      });

      curY += NODE_H + V_GAP;
    }

    // Compute edges: each layer connects to the next layer
    const edgeList: { x1: number; y1: number; x2: number; y2: number }[] = [];
    const layerGroups: NodePos[][] = [];
    for (const node of positioned) {
      if (!layerGroups[node.layerIdx]) layerGroups[node.layerIdx] = [];
      layerGroups[node.layerIdx].push(node);
    }

    const usedLayerIndices = Array.from(new Set(positioned.map((n) => n.layerIdx))).sort((a, b) => a - b);

    for (let i = 0; i < usedLayerIndices.length - 1; i++) {
      const fromLayer = layerGroups[usedLayerIndices[i]];
      const toLayer = layerGroups[usedLayerIndices[i + 1]];
      if (!fromLayer || !toLayer) continue;

      // Connect center of from-layer to center of to-layer (a single bundled arrow)
      const fromCenterX =
        fromLayer.reduce((s, n) => s + n.x + NODE_W / 2, 0) / fromLayer.length;
      const fromBottomY = fromLayer[0].y + NODE_H;

      const toCenterX =
        toLayer.reduce((s, n) => s + n.x + NODE_W / 2, 0) / toLayer.length;
      const toTopY = toLayer[0].y;

      edgeList.push({
        x1: fromCenterX,
        y1: fromBottomY,
        x2: toCenterX,
        y2: toTopY,
      });
    }

    // Compute total canvas size
    const maxX = Math.max(...positioned.map((n) => n.x + NODE_W)) + PAD_X;
    const maxY = curY + PAD_Y;

    return { nodes: positioned, edges: edgeList, width: Math.max(maxX, 400), height: maxY };
  }, []);

  const deptColor = (dept: Department): string => {
    const d = DEPARTMENTS.find((dd) => dd.id === dept);
    if (!d) return "#a1a1aa";
    // Extract a hex-ish color from the tailwind class
    const map: Record<string, string> = {
      marketing: "#8b5cf6",
      sales: "#3b82f6",
      operations: "#10b981",
      finance: "#f59e0b",
      legal: "#64748b",
      engineering: "#06b6d4",
      intelligence: "#f43f5e",
    };
    return map[dept] || "#a1a1aa";
  };

  return (
    <div className="w-full overflow-x-auto border border-surface-200 rounded-xl bg-surface-0">
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        className="block"
        role="img"
        aria-label="Agent pipeline dependency graph"
      >
        {/* Edges */}
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5"
            markerWidth="8" markerHeight="8" orient="auto-start-reverse"
            className="text-surface-300"
          >
            <path d="M 0 0 L 10 5 L 0 10 z" fill="currentColor" />
          </marker>
        </defs>

        {edges.map((e, i) => {
          const midY = (e.y1 + e.y2) / 2;
          return (
            <path
              key={i}
              d={`M ${e.x1} ${e.y1} C ${e.x1} ${midY}, ${e.x2} ${midY}, ${e.x2} ${e.y2}`}
              fill="none"
              stroke="var(--color-surface-300)"
              strokeWidth={1.5}
              markerEnd="url(#arrow)"
              opacity={0.5}
            />
          );
        })}

        {/* Layer labels */}
        {(() => {
          const seen = new Set<number>();
          return nodes.map((node) => {
            if (seen.has(node.layerIdx)) return null;
            seen.add(node.layerIdx);
            const layer = LAYER_ORDER[node.layerIdx];
            return (
              <text
                key={`label-${node.layerIdx}`}
                x={PAD_X}
                y={node.y - 10}
                className="fill-surface-400"
                fontSize={11}
                fontWeight={600}
                fontFamily="var(--font-sans)"
                style={{ textTransform: "uppercase", letterSpacing: "0.05em" }}
              >
                {layer.label}
              </text>
            );
          });
        })()}

        {/* Nodes */}
        {nodes.map((node) => {
          const run = agentRuns[node.agent.id];
          const status: AgentStatus | "idle" = (run?.status as AgentStatus) || "idle";
          const isSelected = selectedAgent === node.agent.id;
          const borderColor = isSelected ? deptColor(node.agent.department) : "var(--color-surface-200)";

          return (
            <g
              key={node.agent.id}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onSelectAgent(node.agent.id)}
              style={{ cursor: "pointer" }}
              role="button"
              aria-label={`${node.agent.label}: ${status}`}
            >
              {/* Card background */}
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                ry={10}
                fill="var(--color-surface-0)"
                stroke={borderColor}
                strokeWidth={isSelected ? 2 : 1}
              />

              {/* Status indicator */}
              <circle
                cx={14}
                cy={NODE_H / 2}
                r={4}
                fill={STATUS_FILL[status]}
              >
                {status === "running" && (
                  <animate attributeName="opacity" values="1;0.4;1" dur="1.5s" repeatCount="indefinite" />
                )}
              </circle>

              {/* Agent icon placeholder */}
              <text
                x={28}
                y={22}
                fontSize={11}
                fontWeight={600}
                fill="var(--color-surface-900)"
                fontFamily="var(--font-sans)"
              >
                {node.agent.label}
              </text>

              {/* Role */}
              <text
                x={28}
                y={38}
                fontSize={9}
                fill="var(--color-surface-400)"
                fontFamily="var(--font-sans)"
              >
                {node.agent.role.length > 22
                  ? node.agent.role.slice(0, 22) + "..."
                  : node.agent.role}
              </text>

              {/* Grade badge */}
              {run?.grade && run.grade !== "—" && (
                <g transform={`translate(${NODE_W - 28}, 8)`}>
                  <rect width={22} height={18} rx={4} fill={STATUS_FILL[status]} opacity={0.15} />
                  <text
                    x={11}
                    y={13}
                    fontSize={9}
                    fontWeight={700}
                    fill={STATUS_FILL[status]}
                    textAnchor="middle"
                    fontFamily="var(--font-mono)"
                  >
                    {run.grade}
                  </text>
                </g>
              )}

              {/* Hover highlight */}
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                ry={10}
                fill="transparent"
                className="hover:fill-surface-50/50"
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}

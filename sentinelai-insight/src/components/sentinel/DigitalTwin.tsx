import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getGraphNodes, getGraphEdges, getBlastRadius, GraphNode, GraphEdge, Incident } from "@/lib/api";

type Status = "healthy" | "warning" | "failure";

interface SectionHeaderProps {
  chip: string;
  chipTint: "purple" | "orange" | "green" | "blue";
  title: string;
  subtitle: string;
}

const chipColorMap = {
  purple: "bg-soft-purple text-soft-purple-ink",
  orange: "bg-soft-orange text-soft-orange-ink",
  green: "bg-soft-green text-soft-green-ink",
  blue: "bg-soft-blue text-soft-blue-ink",
};

export function SectionHeader({ chip, chipTint, title, subtitle }: SectionHeaderProps) {
  return (
    <div className="flex flex-col items-center text-center mb-12 animate-fade-up">
      <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${chipColorMap[chipTint]}`}>
        <span className="live-dot" style={{ background: "currentColor" }} />
        {chip}
      </span>
      <h2 className="font-display mt-5 text-4xl font-semibold tracking-tight text-ink">
        {title}
      </h2>
      <p className="mt-4 text-ink-soft max-w-xl">
        {subtitle}
      </p>
    </div>
  );
}

const NODE_COORDINATES: Record<string, { x: number; y: number }> = {
  "frontend": { x: 40, y: 130 },
  "api-gateway": { x: 170, y: 130 },
  "auth-service": { x: 300, y: 60 },
  "user-service": { x: 300, y: 200 },
  "payment-api": { x: 430, y: 60 },
  "order-service": { x: 430, y: 200 },
  "stripe": { x: 560, y: 30 },
  "redis-cache": { x: 560, y: 110 },
  "postgres-main": { x: 560, y: 190 },
  "kafka": { x: 560, y: 270 },
  "notification": { x: 690, y: 130 },
  "sendgrid": { x: 800, y: 130 }
};

function tintFor(s: Status) {
  return s === "healthy"
    ? { bg: "var(--soft-green)", ink: "var(--soft-green-ink)" }
    : s === "warning"
    ? { bg: "var(--soft-orange)", ink: "var(--soft-orange-ink)" }
    : { bg: "var(--soft-red)", ink: "var(--soft-red-ink)" };
}

interface DigitalTwinProps {
  activeIncident: Incident | null;
}

export function DigitalTwin({ activeIncident }: DigitalTwinProps) {
  const { data: rawNodes, isLoading: loadingNodes } = useQuery<any[]>({
    queryKey: ["graph-nodes"],
    queryFn: getGraphNodes,
    refetchInterval: 10000,
  });

  const { data: rawEdges, isLoading: loadingEdges } = useQuery<any[]>({
    queryKey: ["graph-edges"],
    queryFn: getGraphEdges,
  });

  const nodes = useMemo(() => {
    if (!rawNodes) return [];
    return rawNodes.map((n) => ({
      id: n.id,
      label: n.label,
      type: n.type,
      health: (n.health === "down" ? "failure" : n.health === "degraded" ? "warning" : "healthy") as Status,
      x: NODE_COORDINATES[n.id]?.x ?? 100,
      y: NODE_COORDINATES[n.id]?.y ?? 100,
    }));
  }, [rawNodes]);

  const edges = useMemo(() => {
    if (!rawEdges) return [];
    return rawEdges.map((e) => [e.source, e.target] as [string, string]);
  }, [rawEdges]);

  const [selectedNode, setSelectedNode] = useState<string>("payment-api");
  const [statuses, setStatuses] = useState<Record<string, Status>>({});
  const [simulating, setSimulating] = useState(false);
  const [blastInfo, setBlastInfo] = useState<any>(null);

  // Sync selectedNode when activeIncident changes
  useEffect(() => {
    if (activeIncident && activeIncident.affected_service) {
      const service = activeIncident.affected_service;
      const matched = nodes.find(
        (n) => n.id === service || n.label.toLowerCase() === service.toLowerCase()
      );
      if (matched) {
        setSelectedNode(matched.id);
      }
    }
  }, [activeIncident, nodes]);

  // Sync statuses from db nodes when not simulating
  useEffect(() => {
    if (!simulating && nodes.length > 0) {
      const initial: Record<string, Status> = {};
      nodes.forEach((n) => {
        initial[n.id] = n.health;
      });
      setStatuses(initial);
    }
  }, [nodes, simulating]);

  function reset() {
    const initial: Record<string, Status> = {};
    nodes.forEach((n) => {
      initial[n.id] = n.health;
    });
    setStatuses(initial);
    setBlastInfo(null);
    setSimulating(false);
  }

  async function simulate() {
    if (!selectedNode) return;
    setSimulating(true);
    setBlastInfo(null);

    try {
      const radius = await getBlastRadius(selectedNode);
      setBlastInfo(radius);

      // Visual cascade: start with failing the selected node
      setStatuses((prev) => ({ ...prev, [selectedNode]: "failure" }));

      // Wait and then ripple to direct dependencies
      if (radius.direct_impact.length > 0) {
        await new Promise((r) => setTimeout(r, 800));
        setStatuses((prev) => {
          const next = { ...prev };
          radius.direct_impact.forEach((id: string) => {
            next[id] = "failure";
          });
          return next;
        });
      }

      // Wait and then ripple to indirect dependencies
      if (radius.indirect_dependencies?.length > 0 || radius.indirect_impact?.length > 0) {
        await new Promise((r) => setTimeout(r, 800));
        setStatuses((prev) => {
          const next = { ...prev };
          const indirect = radius.indirect_dependencies || radius.indirect_impact || [];
          indirect.forEach((id: string) => {
            next[id] = "warning";
          });
          return next;
        });
      }
    } catch (e) {
      console.error("Simulation failed", e);
    } finally {
      setSimulating(false);
    }
  }

  const nodeById = useMemo(() => Object.fromEntries(nodes.map((n) => [n.id, n])), [nodes]);

  if (loadingNodes || loadingEdges) {
    return (
      <section id="twin" className="py-28 bg-surface-1">
        <div className="mx-auto max-w-7xl px-6 text-center text-ink-soft">
          Loading live digital twin map...
        </div>
      </section>
    );
  }

  return (
    <section id="twin" className="py-28 bg-surface-1">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Infrastructure Digital Twin"
          chipTint="purple"
          title="A living map of your system."
          subtitle="Every service breathes. Click any node in the graph, then click Simulate to see the BFS blast radius ripple live."
        />
        <div className="card-soft p-6 mt-10 relative overflow-hidden">
          <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
            <div className="flex items-center gap-4 text-xs text-ink-soft">
              <span className="live-dot" /> {nodes.length} services monitored
              {blastInfo && (
                <span className="bg-soft-red text-soft-red-ink px-2 py-0.5 rounded-md font-semibold">
                  Blast Radius Impact: {blastInfo.criticality_score}% (Criticality)
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <select
                value={selectedNode}
                onChange={(e) => setSelectedNode(e.target.value)}
                disabled={simulating}
                className="text-xs px-3 py-1.5 rounded-full border hairline bg-white text-ink font-medium"
              >
                {nodes.map((n) => (
                  <option key={n.id} value={n.id}>
                    Target: {n.label}
                  </option>
                ))}
              </select>
              <button
                onClick={reset}
                className="text-xs px-3 py-1.5 rounded-full border hairline text-ink-soft hover:text-ink"
              >
                Reset
              </button>
              <button
                onClick={simulate}
                disabled={simulating || !selectedNode}
                className="text-xs px-3 py-1.5 rounded-full bg-ink text-white hover:opacity-90 disabled:opacity-60 font-semibold"
              >
                {simulating ? "Simulating BFS…" : "Simulate failure"}
              </button>
            </div>
          </div>

          <div className="relative w-full" style={{ height: 360 }}>
            <svg viewBox="0 0 900 320" className="absolute inset-0 w-full h-full">
              {edges.map(([a, b], i) => {
                const A = nodeById[a];
                const B = nodeById[b];
                if (!A || !B) return null;
                const sA = statuses[a] || "healthy";
                const sB = statuses[b] || "healthy";
                const broken = sA === "failure" || sB === "failure";
                const warn = sA === "warning" || sB === "warning";
                const stroke = broken
                  ? "var(--soft-red-ink)"
                  : warn
                  ? "var(--soft-orange-ink)"
                  : "var(--soft-blue-ink)";
                return (
                  <g key={i}>
                    <line
                      x1={A.x + 40} y1={A.y + 16}
                      x2={B.x + 4} y2={B.y + 16}
                      stroke="var(--surface-5)" strokeWidth="2"
                    />
                    <line
                      x1={A.x + 40} y1={A.y + 16}
                      x2={B.x + 4} y2={B.y + 16}
                      stroke={stroke} strokeWidth="2" opacity="0.55" className="animate-dash"
                    />
                    {!broken && (
                      <circle r="2.5" fill={stroke}>
                      <animate
                        attributeName="cx"
                        values={`${A.x + 40};${B.x + 4}`}
                        dur={`${1.6 + (i % 3) * 0.3}s`}
                        repeatCount="indefinite"
                      />
                      <animate
                        attributeName="cy"
                        values={`${A.y + 16};${B.y + 16}`}
                        dur={`${1.6 + (i % 3) * 0.3}s`}
                        repeatCount="indefinite"
                      />
                    </circle>
                    )}
                  </g>
                );
              })}
            </svg>
            {nodes.map((n) => {
              const s = statuses[n.id] || "healthy";
              const t = tintFor(s);
              const isSelected = selectedNode === n.id;
              return (
                <button
                  key={n.id}
                  onClick={() => setSelectedNode(n.id)}
                  disabled={simulating}
                  className="absolute text-left cursor-pointer transition-all duration-300 hover:scale-105"
                  style={{
                    left: `${(n.x / 900) * 100}%`,
                    top: n.y,
                    width: 130,
                    transform: isSelected ? "scale(1.08)" : undefined,
                  }}
                >
                  <div
                    className="relative rounded-xl border px-3 py-2 bg-white text-sm font-medium text-ink shadow-sm"
                    style={{
                      borderColor: isSelected ? "var(--soft-blue-ink)" : s !== "healthy" ? t.ink : "var(--surface-4)",
                      borderWidth: isSelected ? "2px" : "1px",
                      background: "#fff"
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className="relative inline-block h-2.5 w-2.5 rounded-full"
                        style={{ background: t.ink }}
                      >
                        {s === "failure" && (
                          <span
                            className="absolute inset-0 rounded-full animate-ripple"
                            style={{ background: t.ink }}
                          />
                        )}
                        {s === "warning" && (
                          <span
                            className="absolute inset-0 rounded-full animate-pulse-soft"
                            style={{ background: t.ink, opacity: 0.6 }}
                          />
                        )}
                      </span>
                      <span className="truncate">{n.label}</span>
                    </div>
                    <div
                      className="mt-0.5 text-[9px] uppercase tracking-wider font-semibold"
                      style={{ color: t.ink }}
                    >
                      {s}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
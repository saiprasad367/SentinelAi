import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidents, getReplayEvents, Incident } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

interface IncidentReplayProps {
  activeIncident: Incident | null;
}

const baseHealth: Record<string, number> = {
  healthy: 100,
  latency_spike: 85,
  resource_spike: 78,
  error_rate_rising: 65,
  failure: 30,
  cascade: 25,
  detection: 40,
  investigation: 42,
  mitigation: 75,
  recovery: 88,
  resolved: 100,
};

const dotMap = {
  healthy: "var(--soft-green-ink)",
  warning: "var(--soft-orange-ink)",
  failure: "var(--soft-red-ink)",
} as const;

export function IncidentReplay({ activeIncident }: IncidentReplayProps) {
  const { data: incidents } = useQuery<Incident[]>({
    queryKey: ["incidents-list"],
    queryFn: getIncidents,
  });

  const currentIncident = activeIncident || (incidents && incidents.length > 0 ? incidents[0] : null);

  const [events, setEvents] = useState<any[]>([]);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (currentIncident) {
      const fetchEvents = async () => {
        try {
          const data = await getReplayEvents(currentIncident.id);
          setEvents(data);
          setIdx(0);
        } catch (e) {
          console.error("Failed to fetch replay events", e);
          setEvents([]);
        }
      };
      fetchEvents();
    } else {
      setEvents([]);
    }
  }, [currentIncident]);

  const frames = useMemo(() => {
    if (!events || events.length === 0) {
      return [
        {
          time: "10:00",
          health: 100,
          services: { payment: "healthy", db: "healthy", checkout: "healthy" },
          note: "All systems normal.",
          metrics: { cpu: 18, memory: 32, error_rate: 0, latency_ms: 45 },
        },
        {
          time: "10:05",
          health: 92,
          services: { payment: "warning", db: "healthy", checkout: "healthy" },
          note: "Payment API latency creeping up.",
          metrics: { cpu: 42, memory: 34, error_rate: 0, latency_ms: 540 },
        },
        {
          time: "10:10",
          health: 68,
          services: { payment: "warning", db: "warning", checkout: "healthy" },
          note: "DB connection pool nearing capacity limit.",
          metrics: { cpu: 82, memory: 40, error_rate: 0, latency_ms: 1200 },
        },
        {
          time: "10:15",
          health: 41,
          services: { payment: "failure", db: "warning", checkout: "warning" },
          note: "Payment API connection timeout. Checkout flow blocked.",
          metrics: { cpu: 94, memory: 42, error_rate: 14, latency_ms: 3000 },
        },
        {
          time: "10:20",
          health: 88,
          services: { payment: "healthy", db: "healthy", checkout: "healthy" },
          note: "Automated mitigation playbook applied. Restoring capacity.",
          metrics: { cpu: 22, memory: 35, error_rate: 0, latency_ms: 78 },
        },
      ];
    }

    return events.map((e) => {
      const date = new Date(e.timestamp);
      const timeStr = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const h = baseHealth[e.type] ?? 90;
      
      const sType = ["failure", "cascade"].includes(e.type)
        ? "failure"
        : ["latency_spike", "resource_spike", "error_rate_rising"].includes(e.type)
        ? "warning"
        : "healthy";

      const services = {
        [e.affected_service || "payment-api"]: sType,
        "postgres-main": ["resource_spike", "cascade"].includes(e.type) ? "warning" : "healthy",
        "redis-cache": ["resource_spike"].includes(e.type) ? "warning" : "healthy",
      };

      return {
        time: timeStr,
        health: h,
        services,
        note: `${e.name}: ${e.detail}`,
        metrics: e.metrics || { cpu: 20, memory: 30, error_rate: 0, latency_ms: 80 },
      };
    });
  }, [events]);

  const frame = frames[idx] || frames[0];
  const tintColor = useMemo(
    () => (frame.health < 60 ? "var(--soft-red-ink)" : frame.health < 80 ? "var(--soft-orange-ink)" : "var(--soft-green-ink)"),
    [frame.health],
  );

  return (
    <section id="replay" className="py-28 bg-surface-3">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Incident Replay"
          chipTint="blue"
          title="Rewind the outage. Frame by frame."
          subtitle="Drag the slider to replay how the system degraded and recovered."
        />
        {currentIncident && (
          <div className="mt-4 text-left text-xs text-ink-soft bg-white/50 inline-block px-3 py-1 rounded-full border hairline">
            Replay Focus: <strong>{currentIncident.title}</strong>
          </div>
        )}
        <div className="card-soft p-8 mt-6">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            <div>
              <div className="text-xs uppercase tracking-wider text-ink-soft">Snapshot Time</div>
              <div className="font-display text-4xl font-semibold text-ink tabular-nums">{frame.time}</div>
            </div>
            <div className="flex-1 rounded-xl bg-surface-3 p-4 text-left">
              <div className="text-sm font-semibold text-ink">{frame.note.split(":")[0]}</div>
              <div className="text-xs text-ink-soft mt-1">{frame.note.split(":").slice(1).join(":") || "No additional context."}</div>
            </div>
            <div className="text-right">
              <div className="text-xs uppercase tracking-wider text-ink-soft">Health</div>
              <div className="font-display text-4xl font-semibold tabular-nums" style={{ color: tintColor }}>
                {frame.health}%
              </div>
            </div>
          </div>

          <div className="mt-8">
            <input
              type="range"
              min={0}
              max={frames.length - 1}
              value={idx}
              onChange={(e) => setIdx(Number(e.target.value))}
              className="w-full"
              style={{ accentColor: "var(--ink)" }}
            />
            <div className="mt-2 flex justify-between text-[10px] font-mono text-ink-soft tabular-nums">
              {frames.map((f, i) => (
                <span key={i} className={i === idx ? "font-bold text-ink" : ""}>{f.time}</span>
              ))}
            </div>
          </div>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            {(Object.keys(frame.services) as Array<keyof typeof frame.services>).map((k) => {
              const s = frame.services[k];
              return (
                <div key={k} className="rounded-xl border hairline p-4 bg-white text-left">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: dotMap[s] }} />
                    <span className="text-sm font-medium text-ink capitalize">{k}</span>
                  </div>
                  <div className="mt-1 text-xs uppercase tracking-wider font-semibold" style={{ color: dotMap[s] }}>
                    {s}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Real Telemetry Metrics snapshot */}
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 bg-surface-2 p-4 rounded-xl border border-surface-4 text-left">
            <div>
              <div className="text-[10px] uppercase tracking-wider text-ink-soft font-semibold">CPU Load</div>
              <div className="text-lg font-mono font-bold text-ink mt-1">{frame.metrics.cpu}%</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-ink-soft font-semibold">Memory Usage</div>
              <div className="text-lg font-mono font-bold text-ink mt-1">{frame.metrics.memory}%</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-ink-soft font-semibold">Error Rate</div>
              <div className="text-lg font-mono font-bold text-ink mt-1">{frame.metrics.error_rate}%</div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-ink-soft font-semibold">Response Time</div>
              <div className="text-lg font-mono font-bold text-ink mt-1">{frame.metrics.latency_ms}ms</div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
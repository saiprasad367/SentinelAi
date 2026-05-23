import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidents, resolveIncident, Incident, API_BASE_URL } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

interface ResolutionSimulatorProps {
  activeIncident: Incident | null;
  setActiveIncident: (inc: Incident | null) => void;
}

export function ResolutionSimulator({ activeIncident, setActiveIncident }: ResolutionSimulatorProps) {
  const { data: incidents } = useQuery<Incident[]>({
    queryKey: ["incidents-list"],
    queryFn: getIncidents,
  });

  const currentIncident = activeIncident || (incidents && incidents.length > 0 ? incidents[0] : null);
  const [health, setHealth] = useState(45);
  const [fixing, setFixing] = useState(false);
  const [recs, setRecs] = useState<any[]>([]);

  // Sync health with currentIncident status
  useEffect(() => {
    if (currentIncident) {
      setHealth(currentIncident.status === "resolved" ? 98 : 45);
    } else {
      setHealth(45);
    }
  }, [currentIncident]);

  // Fetch recommendations
  useEffect(() => {
    if (currentIncident) {
      const fetchRecs = async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/impact/${currentIncident.id}/recommendations`);
          if (res.ok) {
            const data = await res.json();
            setRecs(data);
          } else {
            setRecs([]);
          }
        } catch (e) {
          console.error("Failed to fetch recommendations", e);
          setRecs([]);
        }
      };
      fetchRecs();
    } else {
      setRecs([]);
    }
  }, [currentIncident]);

  async function applyFix() {
    if (fixing || !currentIncident) return;
    setFixing(true);
    try {
      const resolved = await resolveIncident(currentIncident.id);
      setActiveIncident(resolved);

      const start = performance.now();
      const from = health;
      const to = 98;
      const dur = 2200;
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / dur);
        const eased = 1 - Math.pow(1 - t, 3);
        setHealth(Math.round(from + (to - from) * eased));
        if (t < 1) requestAnimationFrame(step);
        else setFixing(false);
      };
      requestAnimationFrame(step);
    } catch (e) {
      console.error("Failed to apply suggested fix", e);
      setFixing(false);
    }
  }

  function reset() {
    setHealth(45);
  }

  const tint = health < 60 ? "red" : health < 80 ? "orange" : "green";
  const tintColor = {
    red: "var(--soft-red-ink)",
    orange: "var(--soft-orange-ink)",
    green: "var(--soft-green-ink)",
  }[tint];

  const displayRecs = recs.length > 0 ? recs.map((r) => ({
    t: r.title,
    c: r.source || "AI suggested",
  })) : [
    { t: "Scale DB connection pool 100 → 250", c: "automatic" },
    { t: "Enable circuit breaker on Payment API", c: "automatic" },
    { t: "Redirect 25% checkout traffic to backup region", c: "1-click" },
    { t: "Post status update to /status page", c: "1-click" },
    { t: "Open Jira ticket with full timeline", c: "automatic" },
  ];

  return (
    <section id="resolution" className="py-28 bg-surface-2">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Resolution Simulator"
          chipTint="green"
          title="One click, system recovers."
          subtitle="Apply the suggested fix and watch system health climb in real time."
        />
        <div className="grid lg:grid-cols-[1fr_1.2fr] gap-6 mt-10 items-stretch">
          <div className="card-soft p-8 flex flex-col items-center justify-center bg-surface-1">
            <div className="relative w-64 h-64">
              <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
                <circle cx="100" cy="100" r="84" fill="none" stroke="var(--surface-4)" strokeWidth="14" />
                <circle
                  cx="100"
                  cy="100"
                  r="84"
                  fill="none"
                  stroke={tintColor}
                  strokeWidth="14"
                  strokeLinecap="round"
                  strokeDasharray={`${(health / 100) * 527.79} 527.79`}
                  style={{ transition: "stroke 0.5s, stroke-dasharray 0.2s" }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <div className="text-xs uppercase tracking-wider text-ink-soft">System health</div>
                <div className="font-display text-6xl font-semibold text-ink tabular-nums">{health}%</div>
                <div className="text-xs mt-1" style={{ color: tintColor }}>
                  {health < 60 ? "degraded" : health < 80 ? "recovering" : "healthy"}
                </div>
              </div>
            </div>
            <div className="mt-6 flex gap-2">
              <button
                onClick={applyFix}
                disabled={fixing || !currentIncident}
                className="rounded-full bg-ink text-white text-sm px-5 py-2 hover:opacity-90 disabled:opacity-60"
              >
                {fixing ? "Applying fix…" : "Apply suggested fix"}
              </button>
              <button
                onClick={reset}
                className="rounded-full border hairline text-sm px-5 py-2 text-ink-soft hover:text-ink"
              >
                Reset
              </button>
            </div>
          </div>

          <div className="card-soft p-6">
            <div className="text-sm font-semibold text-ink mb-4">
              Suggested remediation plan
              {currentIncident && (
                <span className="ml-2 font-normal text-xs text-ink-soft">
                  (for {currentIncident.title})
                </span>
              )}
            </div>
            <ol className="space-y-3">
              {displayRecs.map((s, i) => (
                <li key={i} className="flex items-start gap-3 rounded-xl bg-surface-3 p-3">
                  <div className="mt-0.5 h-6 w-6 rounded-full bg-white border hairline flex items-center justify-center text-xs text-ink-soft tabular-nums">
                    {i + 1}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm text-ink">{s.t}</div>
                    <div className="text-xs text-ink-soft">{s.c}</div>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-md bg-soft-green text-soft-green-ink">ready</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
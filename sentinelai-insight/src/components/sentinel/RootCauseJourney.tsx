import { useEffect, useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidents, Incident, API_BASE_URL } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

interface RootCauseJourneyProps {
  activeIncident: Incident | null;
}

const tintMap = {
  red: "bg-soft-red text-soft-red-ink",
  orange: "bg-soft-orange text-soft-orange-ink",
  blue: "bg-soft-blue text-soft-blue-ink",
  green: "bg-soft-green text-soft-green-ink",
} as const;

const dotBg = {
  red: "var(--soft-red-ink)",
  orange: "var(--soft-orange-ink)",
  blue: "var(--soft-blue-ink)",
  green: "var(--soft-green-ink)",
} as const;

export function RootCauseJourney({ activeIncident }: RootCauseJourneyProps) {
  const { data: incidents } = useQuery<Incident[]>({
    queryKey: ["incidents-list"],
    queryFn: getIncidents,
  });

  const currentIncident = activeIncident || (incidents && incidents.length > 0 ? incidents[0] : null);
  const [journeySteps, setJourneySteps] = useState<any[]>([]);
  const [visible, setVisible] = useState(0);

  useEffect(() => {
    if (currentIncident) {
      const fetchJourney = async () => {
        try {
          const invRes = await fetch(`${API_BASE_URL}/investigations/incident/${currentIncident.id}`);
          if (invRes.ok) {
            const invs = await invRes.json();
            if (invs && invs.length > 0) {
              const stepsRes = await fetch(`${API_BASE_URL}/investigations/${invs[0].id}/steps`);
              if (stepsRes.ok) {
                const steps = await stepsRes.json();
                setJourneySteps(steps);
              }
            } else {
              setJourneySteps([]);
            }
          }
        } catch (e) {
          console.error("Failed to fetch journey steps", e);
          setJourneySteps([]);
        }
      };
      fetchJourney();
    } else {
      setJourneySteps([]);
    }
  }, [currentIncident]);

  const displayEvents = useMemo(() => {
    if (!journeySteps || journeySteps.length === 0) {
      return [
        { time: "10:00", title: "Incident detected", detail: "Payment API error rate > 4%", tint: "red" as const },
        { time: "10:01", title: "Latency spike observed", detail: "p95 from 180ms → 1.8s", tint: "orange" as const },
        { time: "10:02", title: "Connection pool exhausted", detail: "DB pool: 100/100 in use", tint: "orange" as const },
        { time: "10:03", title: "Traffic surge correlated", detail: "+312% checkout requests", tint: "blue" as const },
        { time: "10:04", title: "Root cause identified", detail: "Undersized pool + flash sale", tint: "green" as const },
      ];
    }

    return journeySteps
      .sort((a, b) => a.order - b.order)
      .map((s, idx) => {
        let timeStr = "10:00";
        if (s.started_at) {
          timeStr = new Date(s.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        } else {
          const base = currentIncident ? new Date(currentIncident.detected_at) : new Date();
          const shifted = new Date(base.getTime() + idx * 60000);
          timeStr = shifted.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        }

        let tint: "red" | "orange" | "blue" | "green" = "blue";
        if (s.status === "failed") {
          tint = "red";
        } else if (s.status === "completed" && idx === journeySteps.length - 1) {
          tint = "green";
        } else if (s.order <= 2) {
          tint = "red";
        } else if (s.order === 3 || s.order === 4) {
          tint = "orange";
        }

        return {
          time: timeStr,
          title: s.name,
          detail: s.ai_reasoning || s.description || "Diagnostics executing...",
          tint,
        };
      });
  }, [journeySteps, currentIncident]);

  useEffect(() => {
    setVisible(0);
    if (displayEvents.length > 0) {
      let i = 0;
      const tick = () => {
        i++;
        setVisible(i);
        if (i < displayEvents.length) {
          setTimeout(tick, 450);
        }
      };
      const t = setTimeout(tick, 100);
      return () => clearTimeout(t);
    }
  }, [displayEvents]);

  return (
    <section id="root-cause" className="py-28 bg-surface-3">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Root Cause Discovery"
          chipTint="blue"
          title="Detective work, not a one-liner."
          subtitle="SentinelAI shows its reasoning — every clue, in order, with timestamps."
        />
        {currentIncident && (
          <div className="mt-4 text-left text-xs text-ink-soft bg-white/50 inline-block px-3 py-1 rounded-full border hairline">
            Discovery Focus: <strong>{currentIncident.title}</strong>
          </div>
        )}
        <div className="card-soft p-8 mt-6">
          <div className="relative pl-6">
            <div className="absolute left-2 top-2 bottom-2 w-px bg-surface-5" />
            <ol className="space-y-6">
              {displayEvents.map((e, i) => {
                const shown = i < visible;
                return (
                  <li
                    key={i}
                    className={`relative transition-all duration-500 ${
                      shown ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
                    }`}
                  >
                    <span
                      className="absolute -left-[19px] top-1.5 h-3.5 w-3.5 rounded-full border-2 border-white"
                      style={{ background: dotBg[e.tint] }}
                    />
                    <div className="flex flex-col md:flex-row md:items-baseline gap-2 md:gap-6">
                      <span className="font-mono text-xs text-ink-soft tabular-nums w-12 text-left">{e.time}</span>
                      <div className="flex-1 text-left">
                        <div className="font-medium text-ink">{e.title}</div>
                        <div className="text-sm text-ink-soft">{e.detail}</div>
                      </div>
                      <span className={`self-start text-xs px-2 py-1 rounded-md ${tintMap[e.tint]}`}>
                        {e.tint === "green" ? "root cause identified" : "clue"}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ol>
          </div>
        </div>
      </div>
    </section>
  );
}
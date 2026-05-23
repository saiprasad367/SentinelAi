import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidents, API_BASE_URL, Incident } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

const tintMap = {
  red: "bg-soft-red text-soft-red-ink",
  orange: "bg-soft-orange text-soft-orange-ink",
  purple: "bg-soft-purple text-soft-purple-ink",
} as const;

interface BusinessImpactProps {
  activeIncident: Incident | null;
}

export function BusinessImpact({ activeIncident }: BusinessImpactProps) {
  const { data: incidents } = useQuery<Incident[]>({
    queryKey: ["incidents-list"],
    queryFn: getIncidents,
  });

  const latestIncident = activeIncident || (incidents && incidents.length > 0 ? incidents[0] : null);
  const [impactData, setImpactData] = useState<any>(null);

  useEffect(() => {
    if (latestIncident) {
      const fetchImpact = async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/impact/${latestIncident.id}`);
          if (res.ok) {
            const data = await res.json();
            setImpactData(data);
          } else {
            const calcRes = await fetch(`${API_BASE_URL}/impact/${latestIncident.id}`, { method: "POST" });
            if (calcRes.ok) {
              const data = await calcRes.json();
              setImpactData(data);
            }
          }
        } catch (e) {
          console.error("Failed to fetch impact details", e);
        }
      };
      fetchImpact();
    }
  }, [latestIncident]);

  const chain = useMemo(() => {
    if (!latestIncident || !impactData) {
      return [
        { label: "Payment API failure", value: "12 min", sub: "ongoing", tint: "red" as const },
        { label: "Users affected", value: "2,314", sub: "active sessions", tint: "orange" as const },
        { label: "Checkout blocked", value: "61%", sub: "of attempts", tint: "orange" as const },
        { label: "Revenue at risk", value: "$48,200", sub: "per hour", tint: "purple" as const },
        { label: "Urgency", value: "Critical", sub: "P1 escalation", tint: "red" as const },
      ];
    }

    const duration = impactData.duration_minutes ? `${Math.round(impactData.duration_minutes)} min` : "15 min";
    const revenueStr = impactData.revenue_loss_per_minute 
      ? `$${Math.round(impactData.revenue_loss_per_minute * 60).toLocaleString()}` 
      : "$0";

    return [
      {
        label: `${latestIncident.affected_service || "System"} Outage`,
        value: duration,
        sub: latestIncident.status === "resolved" ? "resolved" : "ongoing",
        tint: "red" as const,
      },
      {
        label: "Users affected",
        value: (impactData.affected_users || 0).toLocaleString(),
        sub: "active sessions",
        tint: "orange" as const,
      },
      {
        label: "Impact scale",
        value: `${Math.round(impactData.affected_percentage || 0)}%`,
        sub: "of active load",
        tint: "orange" as const,
      },
      {
        label: "Revenue at risk",
        value: revenueStr,
        sub: "per hour",
        tint: "purple" as const,
      },
      {
        label: "Escalation priority",
        value: impactData.impact_level || "Medium",
        sub: `Urgency score: ${Math.round(impactData.urgency_score || 0)}`,
        tint: "red" as const,
      },
    ];
  }, [latestIncident, impactData]);

  return (
    <section id="impact" className="py-28 bg-surface-3">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Business Impact Story"
          chipTint="orange"
          title="Every incident, translated to dollars."
          subtitle="Real-time translation of service failures to active user degradation and financial loss."
        />
        
        {latestIncident && (
          <div className="mt-4 text-left text-xs text-ink-soft bg-white/50 inline-block px-3 py-1 rounded-full border hairline">
            Active Incident Focus: <strong>{latestIncident.title}</strong>
          </div>
        )}

        <div className="mt-8 grid grid-cols-1 md:grid-cols-5 gap-4">
          {chain.map((c, i) => (
            <div key={c.label} className="relative">
              <div className="card-soft p-5 h-full bg-white border border-surface-4 shadow-sm text-left">
                <span
                  className={`inline-block text-[10px] uppercase font-semibold tracking-wider px-2 py-0.5 rounded ${tintMap[c.tint]}`}
                >
                  step {i + 1}
                </span>
                <div className="mt-3 font-display text-2xl font-semibold text-ink">{c.value}</div>
                <div className="text-sm font-semibold text-ink mt-1 truncate">{c.label}</div>
                <div className="text-xs text-ink-soft mt-0.5">{c.sub}</div>
              </div>
              {i < chain.length - 1 && (
                <div className="hidden md:flex absolute top-1/2 -right-3 -translate-y-1/2 h-6 w-6 items-center justify-center rounded-full bg-white border hairline text-ink-soft z-10 shadow-sm">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
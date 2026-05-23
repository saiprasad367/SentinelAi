import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { getPredictions } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

export function PredictionRadar() {
  const { data: predictions, isLoading } = useQuery({
    queryKey: ["predictions-latest"],
    queryFn: getPredictions,
    refetchInterval: 12000,
  });

  const risks = useMemo(() => {
    if (!predictions || predictions.length === 0) {
      return [
        { label: "Payment CPU", level: 0.72 },
        { label: "Payment Latency", level: 0.88 },
        { label: "Auth Errors", level: 0.4 },
        { label: "DB CPU", level: 0.62 },
        { label: "Cache Memory", level: 0.78 },
        { label: "Gateway Traffic", level: 0.55 },
      ];
    }
    // Take up to 6 unique metric forecasts
    return predictions.slice(0, 6).map((p) => {
      const sName = p.service_name.replace("-service", "").replace("-api", "");
      const label = `${sName.charAt(0).toUpperCase() + sName.slice(1)} ${p.metric_name.toUpperCase()}`;
      return {
        label,
        level: p.outage_probability,
      };
    });
  }, [predictions]);

  const cx = 200;
  const cy = 200;
  const r = 130;
  const n = risks.length;

  const points = useMemo(() => {
    return risks
      .map((risk, i) => {
        const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
        const rr = r * risk.level;
        return `${cx + Math.cos(angle) * rr},${cy + Math.sin(angle) * rr}`;
      })
      .join(" ");
  }, [risks, n, r]);

  if (isLoading) {
    return (
      <section id="radar" className="py-28 bg-surface-1">
        <div className="mx-auto max-w-7xl px-6 text-center text-ink-soft">
          Loading forecasting models...
        </div>
      </section>
    );
  }

  return (
    <section id="radar" className="py-28 bg-surface-1">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="Failure Prediction Radar"
          chipTint="purple"
          title="See failures before they happen."
          subtitle="Continuous forecasting scan across your services. The wider the shape, the closer the threat."
        />
        <div className="grid lg:grid-cols-2 gap-6 mt-10">
          <div className="card-soft p-8 flex items-center justify-center bg-surface-2">
            <svg width="400" height="400" viewBox="0 0 400 400">
              {[0.25, 0.5, 0.75, 1].map((f) => (
                <circle key={f} cx={cx} cy={cy} r={r * f} fill="none" stroke="var(--surface-5)" strokeWidth="1" />
              ))}
              {risks.map((_, i) => {
                const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
                return (
                  <line
                    key={i}
                    x1={cx}
                    y1={cy}
                    x2={cx + Math.cos(angle) * r}
                    y2={cy + Math.sin(angle) * r}
                    stroke="var(--surface-5)"
                    strokeWidth="1"
                  />
                );
              })}
              <defs>
                <linearGradient id="sweep" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="var(--soft-blue-ink)" stopOpacity="0" />
                  <stop offset="100%" stopColor="var(--soft-blue-ink)" stopOpacity="0.35" />
                </linearGradient>
              </defs>
              <g className="animate-radar" style={{ transformOrigin: `${cx}px ${cy}px` }}>
                <path
                  d={`M ${cx} ${cy} L ${cx + r} ${cy} A ${r} ${r} 0 0 0 ${cx + Math.cos(-Math.PI / 3) * r} ${cy + Math.sin(-Math.PI / 3) * r} Z`}
                  fill="url(#sweep)"
                />
              </g>
              <polygon
                points={points}
                fill="var(--soft-blue)"
                stroke="var(--soft-blue-ink)"
                strokeWidth="2"
                opacity="0.75"
              />
              {risks.map((risk, i) => {
                const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
                const rr = r * risk.level;
                return (
                  <circle
                    key={risk.label}
                    cx={cx + Math.cos(angle) * rr}
                    cy={cy + Math.sin(angle) * rr}
                    r="4.5"
                    fill="var(--soft-blue-ink)"
                  />
                );
              })}
              {risks.map((risk, i) => {
                const angle = (Math.PI * 2 * i) / n - Math.PI / 2;
                const lx = cx + Math.cos(angle) * (r + 26);
                const ly = cy + Math.sin(angle) * (r + 20);
                return (
                  <text
                    key={risk.label}
                    x={lx}
                    y={ly}
                    textAnchor="middle"
                    dominantBaseline="middle"
                    fontSize="10"
                    fontWeight="500"
                    fill="var(--ink-soft)"
                  >
                    {risk.label}
                  </text>
                );
              })}
            </svg>
          </div>
          <div className="card-soft p-6">
            <div className="text-sm font-semibold text-ink mb-4">Live Predicted Risks · next 30 min</div>
            <ul className="space-y-3">
              {[...risks]
                .sort((a, b) => b.level - a.level)
                .map((rk) => (
                  <li key={rk.label} className="rounded-xl bg-surface-3 p-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-ink">{rk.label}</span>
                      <span className="text-xs font-mono font-semibold tabular-nums text-ink-soft">
                        {(rk.level * 100).toFixed(0)}% risk
                      </span>
                    </div>
                    <div className="mt-2 h-1.5 rounded-full bg-surface-5 overflow-hidden">
                      <div
                        className="h-full"
                        style={{
                          width: `${rk.level * 100}%`,
                          background:
                            rk.level > 0.75
                              ? "var(--soft-red-ink)"
                              : rk.level > 0.5
                              ? "var(--soft-orange-ink)"
                              : "var(--soft-blue-ink)",
                        }}
                      />
                    </div>
                  </li>
                ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
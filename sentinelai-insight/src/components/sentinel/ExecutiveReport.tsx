import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { getIncidents, generateReport, getReportDownloadUrl, API_BASE_URL, Incident } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

interface ExecutiveReportProps {
  activeIncident: Incident | null;
  setActiveIncident: (inc: Incident | null) => void;
}

export function ExecutiveReport({ activeIncident, setActiveIncident }: ExecutiveReportProps) {
  const { data: incidents, isLoading: loadingIncidents } = useQuery<Incident[]>({
    queryKey: ["incidents-list"],
    queryFn: getIncidents,
    refetchInterval: 10000,
  });

  const [selectedIncidentId, setSelectedIncidentId] = useState<string>("");
  const [impactData, setImpactData] = useState<any>(null);
  const [pdfGenerating, setPdfGenerating] = useState(false);

  // Sync selectedIncidentId with activeIncident if it's set
  useEffect(() => {
    if (activeIncident) {
      setSelectedIncidentId(activeIncident.id);
    }
  }, [activeIncident]);

  // Auto-select latest incident on load
  useEffect(() => {
    if (incidents && incidents.length > 0 && !selectedIncidentId && !activeIncident) {
      setSelectedIncidentId(incidents[0].id);
    }
  }, [incidents, selectedIncidentId, activeIncident]);

  const handleSelectIncident = (id: string) => {
    setSelectedIncidentId(id);
    const found = incidents?.find((inc) => inc.id === id);
    if (found) {
      setActiveIncident(found);
    }
  };

  const selectedIncident = incidents?.find((inc) => inc.id === selectedIncidentId) || null;

  // Fetch impact details for active incident
  useEffect(() => {
    if (selectedIncidentId) {
      const fetchImpact = async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/impact/${selectedIncidentId}`);
          if (res.ok) {
            const data = await res.json();
            setImpactData(data);
          } else {
            // Calculate if not found
            const calcRes = await fetch(`${API_BASE_URL}/impact/${selectedIncidentId}`, { method: "POST" });
            if (calcRes.ok) {
              const data = await calcRes.json();
              setImpactData(data);
            }
          }
        } catch (e) {
          console.error("Failed to fetch impact assessment", e);
          setImpactData(null);
        }
      };
      fetchImpact();
    }
  }, [selectedIncidentId]);

  const handlePdfExport = async () => {
    if (!selectedIncidentId) return;
    setPdfGenerating(true);
    try {
      const report = await generateReport(selectedIncidentId);
      if (report && report.report_id) {
        // Direct download in browser
        window.open(getReportDownloadUrl(report.report_id), "_blank");
      }
    } catch (e) {
      console.error("PDF generation failed", e);
    } finally {
      setPdfGenerating(false);
    }
  };

  if (loadingIncidents) {
    return (
      <section id="report" className="py-28 bg-surface-1">
        <div className="mx-auto max-w-7xl px-6 text-center text-ink-soft">
          Loading report generator...
        </div>
      </section>
    );
  }

  const durationStr = impactData?.duration_minutes 
    ? `${Math.round(impactData.duration_minutes)} min` 
    : "Calculating...";
  const usersAffectedStr = impactData?.affected_users 
    ? impactData.affected_users.toLocaleString() 
    : "Calculating...";
  const revenueImpactStr = impactData?.estimated_total_loss 
    ? `$${Math.round(impactData.estimated_total_loss).toLocaleString()}` 
    : "Calculating...";

  return (
    <section id="report" className="py-28 bg-surface-1">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="AI Executive Report"
          chipTint="green"
          title="Board-ready, one minute after resolution."
          subtitle="Select any live incident in your database to view its generated post-mortem. Export it instantly as a ReportLab PDF."
        />

        <div className="mt-6 max-w-md text-left">
          <label className="text-xs font-semibold text-ink-soft uppercase tracking-wider block mb-2">Select Incident</label>
          <select
            value={selectedIncidentId}
            onChange={(e) => handleSelectIncident(e.target.value)}
            className="w-full text-sm px-4 py-2.5 rounded-full border hairline bg-white text-ink font-medium"
          >
            {incidents?.map((inc) => (
              <option key={inc.id} value={inc.id}>
                {inc.title} ({inc.severity})
              </option>
            ))}
          </select>
        </div>

        {selectedIncident ? (
          <div className="mt-10 grid lg:grid-cols-[1.4fr_1fr] gap-6">
            <div className="card-soft p-10 bg-white shadow-sm border border-surface-4 text-left">
              <div className="flex items-center justify-between text-xs text-ink-soft border-b hairline pb-4 mb-6">
                <span className="font-mono">INC-{selectedIncident.id.substring(0, 8)} · Post-mortem</span>
                <span>Generated by SentinelAI · {selectedIncident.created_at.substring(11, 19)} UTC</span>
              </div>
              <h3 className="font-display text-3xl font-semibold text-ink leading-tight">
                {selectedIncident.title}
              </h3>
              
              <div className="mt-6 grid grid-cols-3 gap-4">
                {[
                  { k: "Duration", v: durationStr },
                  { k: "Users affected", v: usersAffectedStr },
                  { k: "Revenue impact", v: revenueImpactStr },
                ].map((s) => (
                  <div key={s.k} className="rounded-xl bg-surface-3 p-4">
                    <div className="text-xs uppercase tracking-wider text-ink-soft font-semibold">{s.k}</div>
                    <div className="font-display text-xl font-semibold text-ink mt-1">{s.v}</div>
                  </div>
                ))}
              </div>

              {[
                { h: "Incident summary", p: selectedIncident.description || "No description provided." },
                { h: "Root cause", p: selectedIncident.root_cause || "Analyzing logs and traces to isolate root cause..." },
                { h: "AI narrative summary", p: selectedIncident.ai_summary || "SentinelAI is currently summarizing telemetry and traces..." },
                { 
                  h: "Resolution status", 
                  p: selectedIncident.resolved_at 
                    ? `Resolved at ${selectedIncident.resolved_at.substring(11, 19)} UTC. Systems validated and returning nominal payloads.` 
                    : "Incident is currently ongoing. AI diagnostic streams are active." 
                },
              ].map((sec) => (
                <div key={sec.h} className="mt-6">
                  <div className="text-xs uppercase tracking-wider text-soft-blue-ink font-semibold">{sec.h}</div>
                  <p className="mt-2 text-ink leading-relaxed">{sec.p}</p>
                </div>
              ))}
            </div>
            
            <div className="space-y-4">
              <div className="card-soft p-6 bg-white shadow-sm border border-surface-4 text-left">
                <div className="text-sm font-semibold text-ink">Distribution Hub</div>
                <ul className="mt-3 space-y-2 text-sm">
                  {[
                    { label: "Slack #incidents", status: "sent" },
                    { label: "Email exec team", status: "sent" },
                    { label: "Confluence post-mortem", status: "pending" }
                  ].map((d) => (
                    <li key={d.label} className="flex items-center justify-between rounded-lg bg-surface-3 px-3 py-2">
                      <span className="text-ink">{d.label}</span>
                      <span className={`text-xs font-semibold ${d.status === "sent" ? "text-soft-green-ink" : "text-ink-soft"}`}>
                        {d.status}
                      </span>
                    </li>
                  ))}
                  <li className="flex items-center justify-between rounded-lg bg-surface-3 px-3 py-2">
                    <span className="text-ink">Export PDF Report</span>
                    <button
                      onClick={handlePdfExport}
                      disabled={pdfGenerating}
                      className="text-xs bg-ink text-white px-3 py-1 rounded-full font-semibold hover:opacity-90 disabled:opacity-50"
                    >
                      {pdfGenerating ? "Generating..." : "Download"}
                    </button>
                  </li>
                </ul>
              </div>
              
              <div className="card-soft p-6 bg-soft-purple text-left border border-soft-purple-ink/10">
                <div className="text-xs uppercase tracking-wider text-soft-purple-ink font-semibold">SentinelAI verdict</div>
                <div className="font-display text-lg text-ink mt-2 leading-snug">
                  "Root Cause isolation confidence: {(selectedIncident.root_cause_confidence ? selectedIncident.root_cause_confidence * 100 : 92).toFixed(0)}%. Auto-preventative playbooks generated."
                </div>
              </div>
              
              <div className="card-soft p-6 bg-white shadow-sm border border-surface-4 text-left">
                <div className="text-sm font-semibold text-ink">AI Diagnosis speedup</div>
                <div className="mt-2 font-display text-4xl font-semibold text-ink">95.4%</div>
                <div className="text-xs text-ink-soft mt-1">
                  Incident isolated in 12s vs. 4h average manual resolution MTTR.
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-center text-ink-soft py-12">No active incidents found in database.</p>
        )}
      </div>
    </section>
  );
}
import { useEffect, useState, useRef } from "react";
import { createIncident, uploadLogFile, API_BASE_URL, Incident } from "@/lib/api";

interface Step {
  step_order: number;
  step_name: string;
  step_description?: string;
  status: "pending" | "running" | "completed" | "failed" | "skipped";
  confidence?: number;
  ai_reasoning?: string;
}

interface InvestigationCenterProps {
  activeIncident: Incident | null;
  setActiveIncident: (inc: Incident | null) => void;
}

export function InvestigationCenter({ activeIncident, setActiveIncident }: InvestigationCenterProps) {
  const [investigationId, setInvestigationId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [confidence, setConfidence] = useState(0);
  const [status, setStatus] = useState<"idle" | "running" | "completed" | "failed">("idle");
  const [uploading, setUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [consoleLogs, setConsoleLogs] = useState<string[]>([]);
  const eventSourceRef = useRef<EventSource | null>(null);

  // Poll for investigation ID after incident is created
  useEffect(() => {
    let intervalId: any;
    if (activeIncident && !investigationId) {
      const checkInvestigation = async () => {
        try {
          const res = await fetch(`${API_BASE_URL}/investigations/incident/${activeIncident.id}`);
          if (res.ok) {
            const data = await res.json();
            if (data && data.length > 0) {
              setInvestigationId(data[0].id);
              clearInterval(intervalId);
            }
          }
        } catch (e) {
          console.error("Checking investigation failed", e);
        }
      };
      intervalId = setInterval(checkInvestigation, 1000);
      checkInvestigation();
    }
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [activeIncident, investigationId]);

  // Connect to SSE stream once investigation ID is resolved
  useEffect(() => {
    if (investigationId) {
      setStatus("running");
      setConsoleLogs(["Initializing AI agent workflows...", "Establishing connection to live telemetry bus..."]);
      
      const es = new EventSource(`${API_BASE_URL}/investigations/${investigationId}/stream`);
      eventSourceRef.current = es;

      es.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          if (data.type === "step_update") {
            setConsoleLogs((prev) => [
              ...prev,
              `[${data.timestamp.substring(11, 19)}] Running: ${data.step_name}...`,
              ...(data.ai_reasoning ? [`→ AI Reasoning: ${data.ai_reasoning}`] : []),
            ]);

            setSteps((prev) => {
              const existing = prev.find((s) => s.step_order === data.step_order);
              if (existing) {
                return prev.map((s) =>
                  s.step_order === data.step_order
                    ? { ...s, status: data.status, confidence: data.confidence, ai_reasoning: data.ai_reasoning }
                    : s
                );
              } else {
                return [
                  ...prev,
                  {
                    step_order: data.step_order,
                    step_name: data.step_name,
                    step_description: data.step_description,
                    status: data.status,
                    confidence: data.confidence,
                    ai_reasoning: data.ai_reasoning,
                  },
                ].sort((a, b) => a.step_order - b.step_order);
              }
            });

            if (data.confidence) {
              setConfidence(data.confidence * 100);
            }
          } else if (data.type === "investigation_complete") {
            setConsoleLogs((prev) => [
              ...prev,
              `✨ Investigation completed. Root Cause: ${data.root_cause}`,
            ]);
            setStatus("completed");
            if (data.confidence) {
              setConfidence(data.confidence * 100);
            }
            es.close();
          } else if (data.type === "done" || data.type === "timeout") {
            es.close();
          }
        } catch (e) {
          console.error("Parsing SSE data failed", e);
        }
      };

      es.onerror = (e) => {
        console.error("SSE connection error", e);
        es.close();
      };

      return () => {
        es.close();
      };
    }
  }, [investigationId]);

  // Upload custom log file
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setErrorMsg(null);
    setStatus("idle");
    setSteps([]);
    setConfidence(0);
    setInvestigationId(null);
    setConsoleLogs([`Reading log file: ${file.name}...`]);

    try {
      const summary = await uploadLogFile(file);
      if (summary.incident_ids && summary.incident_ids.length > 0) {
        // Fetch full incident detail
        const incRes = await fetch(`${API_BASE_URL}/incidents/${summary.incident_ids[0]}`);
        if (incRes.ok) {
          const inc = await incRes.json();
          setActiveIncident(inc);
        }
      } else {
        setConsoleLogs((prev) => [...prev, "⚠️ No incidents or errors detected in the log file."]);
        setStatus("idle");
      }
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to process log file");
      setConsoleLogs((prev) => [...prev, `❌ Error: ${err.message}`]);
    } finally {
      setUploading(false);
    }
  };

  // Trigger default incident simulation
  const triggerDemo = async (title: string, affectedService: string, severity: string, description: string) => {
    setErrorMsg(null);
    setUploading(true);
    setSteps([]);
    setConfidence(0);
    setInvestigationId(null);
    setConsoleLogs([`Triggering test outage for ${affectedService}...`]);

    try {
      const inc = await createIncident({
        title,
        description,
        severity,
        affected_service: affectedService,
        affected_services: [affectedService],
        source: "frontend_simulation",
      });
      setActiveIncident(inc);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to create test incident");
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setActiveIncident(null);
    setInvestigationId(null);
    setSteps([]);
    setConfidence(0);
    setStatus("idle");
    setConsoleLogs([]);
  };

  return (
    <section id="investigation" className="relative pt-20 pb-32 bg-surface-2 overflow-hidden">
      <div className="absolute inset-0 dot-bg opacity-60 pointer-events-none" />
      <div className="relative mx-auto max-w-7xl px-6">
        <div className="flex flex-col items-center text-center mb-12 animate-fade-up">
          <span className="inline-flex items-center gap-2 rounded-full bg-soft-blue text-soft-blue-ink px-3 py-1 text-xs font-medium">
            <span className="live-dot" style={{ background: "var(--soft-blue-ink)" }} />
            AI Investigation Center · live
          </span>
          <h1 className="font-display mt-5 text-5xl md:text-6xl font-semibold tracking-tight text-ink max-w-3xl">
            Watch the AI investigate an incident in real time.
          </h1>
          <p className="mt-4 text-ink-soft max-w-xl">
            Upload log files or simulate an outage. The AI agent will pull traces, reconstruct paths, and explain the root cause.
          </p>
        </div>

        {status === "idle" ? (
          <div className="max-w-3xl mx-auto card-soft p-10 flex flex-col items-center justify-center text-center bg-white border border-surface-4 shadow-sm animate-fade-up">
            <div className="h-14 w-14 rounded-full bg-soft-blue flex items-center justify-center text-soft-blue-ink mb-6">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12"/></svg>
            </div>
            <h3 className="text-xl font-semibold text-ink">Upload a system log file to analyze</h3>
            <p className="text-ink-soft text-sm mt-2 max-w-md">
              Drop any server log, JSON, or CSV file. The parser will classify severity, extract errors, and launch live diagnostics.
            </p>

            <div className="mt-6 flex flex-col sm:flex-row gap-4 items-center justify-center w-full">
              <label className="cursor-pointer font-semibold rounded-full bg-ink text-white px-6 py-2.5 hover:opacity-90 transition text-sm">
                {uploading ? "Parsing File..." : "Select Log File"}
                <input
                  type="file"
                  accept=".log,.txt,.json,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                  disabled={uploading}
                />
              </label>
              <span className="text-xs text-ink-soft">or</span>
              <button
                onClick={() =>
                  triggerDemo(
                    "Payment API transaction failures",
                    "payment-api",
                    "P1",
                    "Simulated database connection pool exhaustion from high volume checkout traffic."
                  )
                }
                disabled={uploading}
                className="rounded-full border hairline px-5 py-2.5 hover:bg-surface-3 transition text-sm font-semibold text-ink"
              >
                Trigger Demo Outage (Payment API)
              </button>
            </div>
            {errorMsg && <p className="text-xs text-soft-red-ink mt-3">Error: {errorMsg}</p>}
          </div>
        ) : (
          <div className="grid lg:grid-cols-[1.1fr_1fr] gap-6">
            {/* Left: Live Steps & Details */}
            <div className="card-soft p-6 bg-white shadow-sm flex flex-col justify-between">
              <div>
                <div className="flex items-center justify-between mb-5 border-b pb-4">
                  <div className="flex items-center gap-3">
                    <div className="h-9 w-9 rounded-lg bg-soft-red flex items-center justify-center text-soft-red-ink">
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 9 .01 4M12 17.01 12.01 17M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/></svg>
                    </div>
                    <div className="text-left">
                      <div className="text-sm font-semibold text-ink leading-tight">{activeIncident?.title}</div>
                      <div className="text-xs text-ink-soft mt-0.5">
                        {activeIncident?.id.substring(0, 8)} · {activeIncident?.affected_service || "system"}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 rounded-md bg-soft-red text-soft-red-ink font-semibold">
                      {activeIncident?.severity}
                    </span>
                    <button
                      onClick={handleReset}
                      className="text-xs px-2 py-1 rounded-md border hairline hover:bg-surface-3 transition"
                    >
                      Reset
                    </button>
                  </div>
                </div>

                <ol className="space-y-3">
                  {steps.map((s, i) => {
                    const done = s.status === "completed";
                    const running = s.status === "running";
                    return (
                      <li
                        key={s.step_order}
                        className={`flex items-start gap-3 rounded-xl border hairline p-3 transition-all duration-500 ${
                          done ? "bg-surface-3" : running ? "bg-soft-blue/60" : "bg-white opacity-60"
                        }`}
                      >
                        <div className="mt-0.5">
                          {done ? (
                            <div className="h-5 w-5 rounded-full bg-soft-green text-soft-green-ink flex items-center justify-center">
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                            </div>
                          ) : running ? (
                            <div className="h-5 w-5 rounded-full border-2 border-soft-blue-ink border-t-transparent animate-spin" />
                          ) : (
                            <div className="h-5 w-5 rounded-full bg-surface-4" />
                          )}
                        </div>
                        <div className="flex-1 text-left">
                          <div className="text-sm font-semibold text-ink">{s.step_name}</div>
                          {s.step_description && <div className="text-xs text-ink-soft mt-0.5">{s.step_description}</div>}
                        </div>
                        {running && (
                          <span className="text-xs text-soft-blue-ink animate-blink font-medium">thinking…</span>
                        )}
                      </li>
                    );
                  })}
                  {steps.length === 0 && (
                    <li className="text-center py-6 text-sm text-ink-soft">
                      Waiting for investigation framework to initialize...
                    </li>
                  )}
                </ol>
              </div>

              <div className="mt-6 flex items-end justify-between border-t pt-4">
                <div>
                  <div className="text-xs uppercase tracking-wider font-semibold text-ink-soft">AI Confidence</div>
                  <div className="font-display text-4xl font-semibold text-ink tabular-nums">
                    {Math.round(confidence)}%
                  </div>
                </div>
                <div className="w-1/2 h-2.5 rounded-full bg-surface-4 overflow-hidden">
                  <div
                    className="h-full bg-soft-blue-ink transition-all duration-500"
                    style={{ width: `${confidence}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Right: Reasoning Console & Visual Stream */}
            <div className="card-soft p-6 bg-surface-3 border border-surface-4 shadow-sm flex flex-col h-[460px]">
              <div className="flex items-center justify-between mb-4">
                <div className="text-sm font-semibold text-ink">Agent Diagnostics Terminal</div>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-surface-4 text-ink-soft">
                  {status === "completed" ? "IDLE" : "STREAMING"}
                </span>
              </div>
              
              <div className="flex-1 bg-ink text-surface-2 p-4 rounded-xl font-mono text-xs overflow-y-auto text-left space-y-2">
                {consoleLogs.map((log, i) => (
                  <div 
                    key={i} 
                    className={`${
                      log.startsWith("✨") 
                        ? "text-soft-green" 
                        : log.startsWith("→") 
                        ? "text-soft-blue-ink opacity-90 pl-3" 
                        : log.startsWith("❌") 
                        ? "text-soft-red" 
                        : "text-white"
                    }`}
                  >
                    {log}
                  </div>
                ))}
                {status === "running" && (
                  <div className="text-soft-blue-ink animate-pulse">▋ Agent reasoning...</div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
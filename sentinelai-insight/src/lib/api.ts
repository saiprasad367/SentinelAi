// SentinelAI — Frontend API Client
// Connects to the Modular Monolith FastAPI backend on port 8000

export const BACKEND_URL = "http://localhost:8000";
export const API_BASE_URL = `${BACKEND_URL}/api/v1`;

export interface Incident {
  id: string;
  title: string;
  description?: string;
  severity: string;
  status: string;
  affected_service?: string;
  affected_services: string[];
  root_cause?: string;
  root_cause_confidence?: number;
  ai_summary?: string;
  tags: string[];
  source?: string;
  detected_at: string;
  resolved_at?: string;
  created_at: string;
}

export interface GraphNode {
  id: string;
  node_id: string;
  label: string;
  node_type: string;
  health_status: string;
  criticality: number;
  meta_data?: any;
}

export interface GraphEdge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  edge_type: string;
  weight: number;
  latency_ms?: number;
  meta_data?: any;
}

export interface Prediction {
  id: string;
  service_name: string;
  metric_name: string;
  outage_probability: number;
  confidence: number;
  risk_score: number;
  predicted_outage_time?: string;
  time_to_failure_minutes?: number;
  current_value?: number;
  baseline_value?: number;
  anomaly_score?: number;
}

export interface MemoryEntry {
  id: string;
  incident_id: string;
  title: string;
  description?: string;
  root_cause?: string;
  resolution?: string;
  affected_services: string[];
  tags: string[];
  severity?: string;
  created_at: string;
  similarity?: number;
}

// ─── API Methods ─────────────────────────────────────────────────────────────

// Incidents
export async function getIncidents(): Promise<Incident[]> {
  const res = await fetch(`${API_BASE_URL}/incidents?page_size=20`);
  if (!res.ok) throw new Error("Failed to fetch incidents");
  const data = await res.json();
  return data.incidents || [];
}

export async function createIncident(payload: Partial<Incident>): Promise<Incident> {
  const res = await fetch(`${API_BASE_URL}/incidents`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error("Failed to create incident");
  return res.json();
}

export async function uploadLogFile(file: File): Promise<any> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE_URL}/incidents/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error("Failed to upload log file");
  return res.json();
}

// Graph
export async function getGraphNodes(): Promise<GraphNode[]> {
  const res = await fetch(`${API_BASE_URL}/graph/nodes`);
  if (!res.ok) throw new Error("Failed to fetch graph nodes");
  return res.json();
}

export async function getGraphEdges(): Promise<GraphEdge[]> {
  const res = await fetch(`${API_BASE_URL}/graph/edges`);
  if (!res.ok) throw new Error("Failed to fetch graph edges");
  return res.json();
}

export async function getBlastRadius(serviceName: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/graph/blast-radius/${serviceName}`);
  if (!res.ok) throw new Error("Failed to fetch blast radius");
  return res.json();
}

// Predictions
export async function getPredictions(): Promise<Prediction[]> {
  const res = await fetch(`${API_BASE_URL}/predictions/latest`);
  if (!res.ok) throw new Error("Failed to fetch predictions");
  return res.json();
}

// Memory Semantic Search
export async function searchMemories(query: string): Promise<MemoryEntry[]> {
  const res = await fetch(`${API_BASE_URL}/memory/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: 5 }),
  });
  if (!res.ok) throw new Error("Failed to search memories");
  return res.json();
}

// Recommendations
export async function getImpactAndRecommendations(incidentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/impact/${incidentId}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to fetch impact & recommendations");
  return res.json();
}

// Replay events
export async function getReplayEvents(incidentId: string): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/replay/${incidentId}/events`);
  if (!res.ok) throw new Error("Failed to fetch replay events");
  return res.json();
}

// Recommendations and resolution
export async function getRecommendations(incidentId: string): Promise<any[]> {
  const res = await fetch(`${API_BASE_URL}/impact/${incidentId}/recommendations`);
  if (!res.ok) throw new Error("Failed to fetch recommendations");
  return res.json();
}

export async function resolveIncident(incidentId: string): Promise<Incident> {
  const res = await fetch(`${API_BASE_URL}/incidents/${incidentId}/resolve`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to resolve incident");
  return res.json();
}

// PDF Post-Mortem Generation
export async function generateReport(incidentId: string): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/reports/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ incident_id: incidentId, report_type: "postmortem" }),
  });
  if (!res.ok) throw new Error("Failed to generate report");
  return res.json();
}

export function getReportDownloadUrl(reportId: string): string {
  return `${API_BASE_URL}/reports/${reportId}/download`;
}

// Analytics
export async function getAnalyticsSummary(): Promise<any> {
  const res = await fetch(`${API_BASE_URL}/analytics/summary`);
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

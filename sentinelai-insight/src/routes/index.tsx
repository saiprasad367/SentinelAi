import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Navbar } from "@/components/sentinel/Navbar";
import { InvestigationCenter } from "@/components/sentinel/InvestigationCenter";
import { DigitalTwin } from "@/components/sentinel/DigitalTwin";
import { RootCauseJourney } from "@/components/sentinel/RootCauseJourney";
import { PredictionRadar } from "@/components/sentinel/PredictionRadar";
import { BusinessImpact } from "@/components/sentinel/BusinessImpact";
import { MemoryBrain } from "@/components/sentinel/MemoryBrain";
import { ResolutionSimulator } from "@/components/sentinel/ResolutionSimulator";
import { IncidentReplay } from "@/components/sentinel/IncidentReplay";
import { ExecutiveReport } from "@/components/sentinel/ExecutiveReport";
import { Footer } from "@/components/sentinel/Footer";
import { Incident } from "@/lib/api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "SentinelAI — AI on-call for production systems" },
      {
        name: "description",
        content:
          "SentinelAI investigates incidents, finds root causes, predicts failures, and writes the post-mortem — automatically.",
      },
      { property: "og:title", content: "SentinelAI — AI on-call for production systems" },
      {
        property: "og:description",
        content:
          "Watch the AI investigate, simulate, and resolve incidents in real time. A mission-control experience for SRE.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const [activeIncident, setActiveIncident] = useState<Incident | null>(null);

  return (
    <div className="min-h-screen bg-surface-2 text-ink">
      <Navbar />
      <main>
        <InvestigationCenter activeIncident={activeIncident} setActiveIncident={setActiveIncident} />
        <DigitalTwin activeIncident={activeIncident} />
        <RootCauseJourney activeIncident={activeIncident} />
        <PredictionRadar />
        <BusinessImpact activeIncident={activeIncident} />
        <MemoryBrain />
        <ResolutionSimulator activeIncident={activeIncident} setActiveIncident={setActiveIncident} />
        <IncidentReplay activeIncident={activeIncident} />
        <ExecutiveReport activeIncident={activeIncident} setActiveIncident={setActiveIncident} />
      </main>
      <Footer />
    </div>
  );
}

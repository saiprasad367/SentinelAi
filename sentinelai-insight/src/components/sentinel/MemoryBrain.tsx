import { useState } from "react";
import { searchMemories, MemoryEntry } from "@/lib/api";
import { SectionHeader } from "./DigitalTwin";

const clusters = [
  {
    id: "db",
    label: "Database failures",
    count: 14,
    tint: "blue" as const,
    x: 22,
    y: 30,
    size: 150,
    memories: ["Pool exhaustion (Mar 14)", "Replica lag spike (Feb 02)", "Deadlock storm (Jan 19)"],
  },
  {
    id: "deploy",
    label: "Deployment incidents",
    count: 9,
    tint: "purple" as const,
    x: 60,
    y: 24,
    size: 130,
    memories: ["Bad migration (Apr 04)", "Env var missing (Mar 22)", "Canary rollback (Feb 10)"],
  },
  {
    id: "cache",
    label: "Cache issues",
    count: 6,
    tint: "green" as const,
    x: 72,
    y: 65,
    size: 110,
    memories: ["Redis OOM (Mar 28)", "Stampede on launch (Feb 16)"],
  },
  {
    id: "api",
    label: "API timeouts",
    count: 11,
    tint: "orange" as const,
    x: 32,
    y: 70,
    size: 140,
    memories: ["Upstream 3rd party (Apr 11)", "Slow query (Mar 09)", "Network partition (Feb 24)"],
  },
];

const tintMap = {
  blue: { bg: "var(--soft-blue)", ink: "var(--soft-blue-ink)" },
  purple: { bg: "var(--soft-purple)", ink: "var(--soft-purple-ink)" },
  green: { bg: "var(--soft-green)", ink: "var(--soft-green-ink)" },
  orange: { bg: "var(--soft-orange)", ink: "var(--soft-orange-ink)" },
};

export function MemoryBrain() {
  const [active, setActive] = useState<string>("db");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<MemoryEntry[] | null>(null);
  const [searching, setSearching] = useState(false);

  const activeCluster = clusters.find((c) => c.id === active) ?? clusters[0];
  const t = tintMap[activeCluster.tint];

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    setSearchResults([]);

    try {
      const results = await searchMemories(searchQuery);
      setSearchResults(results);
    } catch (err) {
      console.error("Semantic search failed", err);
    } finally {
      setSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
  };

  return (
    <section id="memory" className="py-28 bg-surface-1">
      <div className="mx-auto max-w-7xl px-6">
        <SectionHeader
          chip="AI Memory Brain"
          chipTint="purple"
          title="It remembers every incident, so you don't have to."
          subtitle="Similar incidents cluster together. Search your memories semantically using pgvector vector embeddings."
        />
        
        {/* Semantic Search Box */}
        <div className="mt-8 max-w-2xl">
          <form onSubmit={handleSearch} className="flex gap-2">
            <input
              type="text"
              placeholder="Search past incidents (e.g., 'database connection pool exhaustion' or 'redis oom')"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="flex-1 text-sm px-4 py-2.5 rounded-full border hairline bg-white text-ink font-medium focus:outline-none focus:ring-2 focus:ring-soft-blue-ink"
            />
            <button
              type="submit"
              disabled={searching}
              className="bg-ink text-white text-xs px-5 py-2.5 rounded-full font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {searching ? "Searching..." : "Search"}
            </button>
            {searchResults && (
              <button
                type="button"
                onClick={clearSearch}
                className="border hairline text-ink-soft text-xs px-4 py-2.5 rounded-full hover:bg-surface-3"
              >
                Clear
              </button>
            )}
          </form>
        </div>

        <div className="grid lg:grid-cols-[1.4fr_1fr] gap-6 mt-6">
          {searchResults ? (
            <div className="card-soft p-6 bg-white overflow-y-auto" style={{ height: 460 }}>
              <div className="text-sm font-semibold text-ink mb-4 flex items-center justify-between">
                <span>Semantic Matches for: "{searchQuery}"</span>
                <span className="text-xs text-ink-soft">{searchResults.length} results</span>
              </div>
              <div className="space-y-4">
                {searchResults.map((entry, idx) => (
                  <div key={entry.id || idx} className="rounded-xl border hairline p-4 bg-surface-3 text-left">
                    <div className="flex items-center justify-between">
                      <span className="text-xs px-2 py-0.5 rounded bg-soft-blue text-soft-blue-ink font-semibold">
                        {(entry.similarity ? entry.similarity * 100 : 92).toFixed(1)}% Match
                      </span>
                      <span className="text-xs text-ink-soft">
                        {entry.created_at ? entry.created_at.substring(0, 10) : "Historical"}
                      </span>
                    </div>
                    <h4 className="font-semibold text-ink mt-2 text-sm">{entry.title}</h4>
                    {entry.root_cause && (
                      <p className="text-xs text-ink mt-1 font-medium bg-white/70 p-2 rounded-lg border hairline">
                        <strong className="text-soft-blue-ink">Root Cause:</strong> {entry.root_cause}
                      </p>
                    )}
                    {entry.resolution && (
                      <p className="text-xs text-ink-soft mt-1">
                        <strong>Resolution:</strong> {entry.resolution}
                      </p>
                    )}
                  </div>
                ))}
                {searchResults.length === 0 && (
                  <p className="text-center py-12 text-sm text-ink-soft">
                    No matching historical incidents found.
                  </p>
                )}
              </div>
            </div>
          ) : (
            <div className="card-soft p-6 relative overflow-hidden bg-white border border-surface-4" style={{ height: 460 }}>
              <div className="absolute inset-0 dot-bg opacity-50" />
              {clusters.map((c, i) => {
                const ct = tintMap[c.tint];
                const isActive = c.id === active;
                return (
                  <button
                    key={c.id}
                    onClick={() => setActive(c.id)}
                    className="absolute rounded-full text-left transition-all duration-500 animate-float"
                    style={{
                      left: `${c.x}%`,
                      top: `${c.y}%`,
                      width: c.size,
                      height: c.size,
                      marginLeft: -c.size / 2,
                      marginTop: -c.size / 2,
                      background: ct.bg,
                      border: `1px solid ${isActive ? ct.ink : "var(--surface-5)"}`,
                      boxShadow: isActive
                        ? `0 12px 30px -10px ${ct.ink}88`
                        : "0 6px 18px -8px rgba(17,17,17,0.08)",
                      transform: `scale(${isActive ? 1.06 : 1})`,
                      animationDelay: `${i * 400}ms`,
                    }}
                  >
                    <div className="h-full w-full rounded-full flex flex-col items-center justify-center px-4 text-center">
                      <div className="text-[10px] uppercase tracking-wider font-semibold" style={{ color: ct.ink }}>
                        {c.count} memories
                      </div>
                      <div className="font-medium text-ink text-sm mt-1">{c.label}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <div className="card-soft p-6 bg-white shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 border-b pb-4 mb-4">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: t.ink }} />
                <div className="text-sm font-semibold text-ink">{activeCluster.label}</div>
                <span className="ml-auto text-xs text-ink-soft">{activeCluster.count} entries</span>
              </div>
              <div className="space-y-2">
                {activeCluster.memories.map((m, i) => (
                  <div
                    key={m}
                    className="rounded-xl bg-surface-3 px-3 py-2.5 text-sm text-ink flex items-center justify-between animate-fade-up text-left"
                    style={{ animationDelay: `${i * 80}ms` }}
                  >
                    <span>{m}</span>
                    <span className="text-xs text-ink-soft">recalled</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="mt-5 rounded-xl bg-soft-blue p-3 text-xs text-soft-blue-ink text-left">
              SentinelAI cross-references vector embeddings against these memory clusters during every live root-cause workflow.
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
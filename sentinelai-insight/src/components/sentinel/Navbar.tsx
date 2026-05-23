import { Link } from "@tanstack/react-router";

export function Navbar() {
  return (
    <header className="sticky top-0 z-50 backdrop-blur-lg bg-white/70 border-b hairline">
      <div className="mx-auto max-w-7xl px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 font-display font-semibold text-ink">
          <span className="relative inline-flex h-7 w-7 items-center justify-center rounded-lg bg-soft-blue text-soft-blue-ink">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5z"/></svg>
          </span>
          SentinelAI
        </Link>
        <nav className="hidden md:flex items-center gap-7 text-sm text-ink-soft">
          <a href="#investigation" className="hover:text-ink">Investigation</a>
          <a href="#twin" className="hover:text-ink">Digital Twin</a>
          <a href="#root-cause" className="hover:text-ink">Root Cause</a>
          <a href="#radar" className="hover:text-ink">Prediction</a>
          <a href="#impact" className="hover:text-ink">Impact</a>
          <a href="#memory" className="hover:text-ink">Memory</a>
          <a href="#report" className="hover:text-ink">Report</a>
        </nav>
        <div className="flex items-center gap-2">
          <span className="hidden sm:inline-flex items-center gap-2 rounded-full bg-surface-4 px-3 py-1 text-xs text-ink-soft">
            <span className="live-dot" /> Live
          </span>
          <button className="rounded-full bg-ink text-white text-sm px-4 py-1.5 hover:opacity-90 transition">
            Watch demo
          </button>
        </div>
      </div>
    </header>
  );
}
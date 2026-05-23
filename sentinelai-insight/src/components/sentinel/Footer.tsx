export function Footer() {
  return (
    <footer className="border-t hairline bg-surface-2 py-10">
      <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm text-ink-soft">
          <span className="inline-flex h-6 w-6 items-center justify-center rounded-md bg-soft-blue text-soft-blue-ink">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 2 4 5v6c0 5 3.5 9.5 8 11 4.5-1.5 8-6 8-11V5z"/></svg>
          </span>
          <span className="text-ink font-medium">SentinelAI</span>
          <span>· AI on-call for production systems</span>
        </div>
        <div className="text-xs text-ink-soft">© {new Date().getFullYear()} SentinelAI · Built for engineers who sleep at night.</div>
      </div>
    </footer>
  );
}
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Search, Clock, TrendingUp } from "lucide-react";

export default function ResearchLandingPage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [recent, setRecent] = useState<string[]>([]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem("kafin_recent_research") || "[]";
      const parsed = JSON.parse(raw);
      setRecent(parsed);
    } catch {}
  }, []);

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const ticker = query.trim().toUpperCase();
    if (!ticker) return;
    router.push(`/research/${ticker}`);
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-8">
      <div className="text-center">
        <TrendingUp size={40} className="mx-auto mb-4 text-[var(--accent-blue)]" />
        <h1 className="text-3xl font-bold text-[var(--text-primary)]">Research</h1>
        <p className="text-[var(--text-secondary)] mt-2">
          Ticker eingeben für vollständiges Trading-Research
        </p>
      </div>

      <form onSubmit={handleSearch} className="w-full max-w-md">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              type="text"
              value={query}
              onChange={e => setQuery(e.target.value.toUpperCase())}
              placeholder="Ticker eingeben (z.B. XOM, NVDA, AAPL)"
              autoFocus
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)]
                         pl-10 pr-4 py-3 text-lg font-mono text-[var(--text-primary)]
                         placeholder:text-[var(--text-muted)] placeholder:font-sans
                         placeholder:text-sm outline-none focus:border-[var(--accent-blue)]"
            />
          </div>
          <button
            type="submit"
            disabled={!query.trim()}
            className="rounded-xl bg-[var(--accent-blue)] px-6 py-3 text-sm font-semibold
                       text-white hover:opacity-90 disabled:opacity-40 transition-all"
          >
            Research
          </button>
        </div>
      </form>

      {recent.length > 0 && (
        <div className="w-full max-w-md">
          <p className="text-xs text-[var(--text-muted)] flex items-center gap-1.5 mb-3">
            <Clock size={11} /> Zuletzt angesehen
          </p>
          <div className="flex flex-wrap gap-2">
            {recent.map(t => (
              <button
                key={t}
                onClick={() => router.push(`/research/${t}`)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)]
                           px-3 py-1.5 text-sm font-mono text-[var(--text-primary)]
                           hover:bg-[var(--bg-tertiary)] transition-all"
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

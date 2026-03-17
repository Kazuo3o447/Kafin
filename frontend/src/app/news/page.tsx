"use client";

import { useState, useEffect } from "react";
import { Newspaper, Play, Filter } from "lucide-react";
import { api } from "@/lib/api";

type NewsBullet = {
  id?: string;
  ticker?: string;
  category?: string;
  bullet_text?: string;
  sentiment_score?: number;
  is_material?: boolean;
  created_at?: string;
};

export default function NewsPage() {
  const [news, setNews] = useState<NewsBullet[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTicker, setFilterTicker] = useState("");
  const [filterSentiment, setFilterSentiment] = useState<"all" | "positive" | "negative">("all");
  const [filterMaterial, setFilterMaterial] = useState(false);
  const [scanResult, setScanResult] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);

  useEffect(() => {
    loadNews();
    loadWatchlist();
  }, []);

  async function loadWatchlist() {
    try {
      const data = await api.getWatchlist();
      setWatchlist(data);
    } catch (error) {
      console.error("Watchlist fetch error", error);
    }
  }

  async function loadNews() {
    try {
      const wl = await api.getWatchlist();
      const allNews: NewsBullet[] = [];

      for (const item of wl) {
        try {
          const data = await api.getNewsMemory(item.ticker);
          if (data.bullet_points) {
            allNews.push(...data.bullet_points);
          }
        } catch (error) {
          console.error(`News fetch error for ${item.ticker}`, error);
        }
      }

      allNews.sort((a, b) => {
        const dateA = a.created_at ? new Date(a.created_at).getTime() : 0;
        const dateB = b.created_at ? new Date(b.created_at).getTime() : 0;
        return dateB - dateA;
      });

      setNews(allNews);
    } catch (error) {
      console.error("News load error", error);
    } finally {
      setLoading(false);
    }
  }

  async function runNewsScan() {
    setLoading(true);
    setScanResult("News-Scan läuft...");
    try {
      const result = await api.runNewsScan();
      setScanResult(`News-Scan abgeschlossen. ${result.results?.length || 0} Ticker gescannt.`);
      loadNews();
    } catch (error) {
      setScanResult("Fehler beim News-Scan.");
    } finally {
      setLoading(false);
    }
  }

  async function runSecScan() {
    setLoading(true);
    setScanResult("SEC-Scan läuft...");
    try {
      const result = await api.runSecScan();
      setScanResult(`SEC-Scan abgeschlossen. ${result.filings_found || 0} Filings gefunden.`);
      loadNews();
    } catch (error) {
      setScanResult("Fehler beim SEC-Scan.");
    } finally {
      setLoading(false);
    }
  }

  async function runMacroScan() {
    setLoading(true);
    setScanResult("Makro-Scan läuft...");
    try {
      const result = await api.runMacroScan();
      setScanResult(`Makro-Scan abgeschlossen. ${result.stats?.events_saved || 0} Events gespeichert.`);
      loadNews();
    } catch (error) {
      setScanResult("Fehler beim Makro-Scan.");
    } finally {
      setLoading(false);
    }
  }

  const filtered = news.filter((item) => {
    if (filterTicker && item.ticker !== filterTicker) return false;
    if (filterMaterial && !item.is_material) return false;
    if (filterSentiment === "positive" && (item.sentiment_score ?? 0) <= 0.3) return false;
    if (filterSentiment === "negative" && (item.sentiment_score ?? 0) >= -0.3) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">News</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">News-Timeline</h1>
        <p className="text-sm text-[var(--text-secondary)]">Alle News-Stichpunkte aus der Watchlist</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Filter size={16} className="text-[var(--text-muted)]" />
            <select
              value={filterTicker}
              onChange={(e) => setFilterTicker(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-1 text-sm text-[var(--text-primary)] outline-none"
            >
              <option value="">Alle Ticker</option>
              {watchlist.map((item) => (
                <option key={item.ticker} value={item.ticker}>
                  {item.ticker}
                </option>
              ))}
            </select>
            <select
              value={filterSentiment}
              onChange={(e) => setFilterSentiment(e.target.value as any)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-1 text-sm text-[var(--text-primary)] outline-none"
            >
              <option value="all">Alle Sentiments</option>
              <option value="positive">Positiv</option>
              <option value="negative">Negativ</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={filterMaterial}
                onChange={(e) => setFilterMaterial(e.target.checked)}
                className="rounded border-[var(--border)]"
              />
              Nur Material Events
            </label>
          </div>

          <div className="max-h-[700px] space-y-3 overflow-y-auto rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-4">
            {loading ? (
              <p className="text-sm text-[var(--text-muted)]">Lade News...</p>
            ) : filtered.length === 0 ? (
              <p className="text-sm text-[var(--text-muted)]">Keine News-Stichpunkte gefunden.</p>
            ) : (
              filtered.map((item, idx) => (
                <div
                  key={item.id || idx}
                  className={`rounded-lg border p-4 ${
                    item.is_material
                      ? "border-[var(--accent-red)] bg-red-900/10"
                      : "border-[var(--border)] bg-[var(--bg-tertiary)]"
                  }`}
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-[var(--bg-elevated)] px-2 py-1 font-semibold text-[var(--text-primary)]">
                        {item.ticker}
                      </span>
                      <span className="rounded bg-[var(--bg-elevated)] px-2 py-1 text-[var(--text-muted)]">
                        {item.category || "News"}
                      </span>
                      {item.is_material && (
                        <span className="rounded bg-[var(--accent-red)] px-2 py-1 font-semibold text-white">
                          TORPEDO
                        </span>
                      )}
                    </div>
                    <span
                      className={`font-semibold ${
                        (item.sentiment_score ?? 0) > 0.3
                          ? "text-[var(--accent-green)]"
                          : (item.sentiment_score ?? 0) < -0.3
                          ? "text-[var(--accent-red)]"
                          : "text-[var(--text-muted)]"
                      }`}
                    >
                      {item.sentiment_score?.toFixed(2) || "0.00"}
                    </span>
                  </div>
                  <p className="mt-3 text-sm text-[var(--text-primary)]">{item.bullet_text}</p>
                  <p className="mt-2 text-xs text-[var(--text-muted)]">
                    {item.created_at ? new Date(item.created_at).toLocaleString("de-DE") : "-"}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
            <div className="flex items-center gap-2 text-[var(--text-muted)]">
              <Newspaper size={16} />
              <h2 className="text-sm font-semibold uppercase tracking-[0.3em]">Scan-Aktionen</h2>
            </div>
            <div className="mt-4 space-y-3">
              <button
                onClick={runNewsScan}
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                <Play size={16} />
                News-Scan jetzt
              </button>
              <button
                onClick={runSecScan}
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-amber)] px-4 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                <Play size={16} />
                SEC-Scan jetzt
              </button>
              <button
                onClick={runMacroScan}
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-purple)] px-4 py-3 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                <Play size={16} />
                Makro-Scan jetzt
              </button>
            </div>
            {scanResult && (
              <div className="mt-4 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] p-3 text-sm text-[var(--text-primary)]">
                {scanResult}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

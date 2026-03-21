"use client";

import { useState, useEffect, useCallback } from "react";
import { Newspaper, Play, Filter, Circle, Activity, Radar, Sparkles, Globe } from "lucide-react";
import { api } from "@/lib/api";
import { cachedFetch, cacheAge, cacheInvalidate, cacheInvalidateAll } from "@/lib/clientCache";
import { CacheStatus } from "@/components/CacheStatus";

type NewsBullet = {
  id?: string;
  ticker?: string;
  category?: string;
  bullet_text?: string;
  sentiment_score?: number;
  is_material?: boolean;
  created_at?: string;
};

type SignalItem = {
  ticker: string;
  type: string;
  alert_text: string;
};

type GoogleNewsItem = {
  headline: string;
  source: string;
  url: string;
  category: string;
  related_ticker?: string;
  sentiment_score?: number;
};

export default function NewsPage() {
  const [news, setNews] = useState<NewsBullet[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTicker, setFilterTicker] = useState("");
  const [filterSentiment, setFilterSentiment] = useState<"all" | "positive" | "negative">("all");
  const [filterMaterial, setFilterMaterial] = useState(false);
  const [scanResult, setScanResult] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"news" | "google" | "signals">("news");
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [signalStatus, setSignalStatus] = useState<string>("");
  const [signalLoading, setSignalLoading] = useState(false);
  const [googleNews, setGoogleNews] = useState<GoogleNewsItem[]>([]);
  const [googleStatus, setGoogleStatus] = useState("");
  const [googleLoading, setGoogleLoading] = useState(false);
  const [fromCache, setFromCache] = useState(false);
  const [dataAge, setDataAge] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadNews();
    loadWatchlist();
  }, []);

  const loadWatchlist = useCallback(async (invalidate = false) => {
    if (invalidate) cacheInvalidate('news:watchlist');
    try {
      const { data } = await cachedFetch("news:watchlist", () => api.getWatchlist(), 300);
      setWatchlist(data || []);
    } catch (error) {
      console.error("Watchlist fetch error", error);
    }
  }, []);

  async function runGoogleNewsScan() {
    setGoogleLoading(true);
    setGoogleStatus("Google News Scan läuft...");
    try {
      const result = await api.scanGoogleNews();
      setGoogleNews(result.articles || []);
      setGoogleStatus(`Google News Scan: ${result.count || 0} Artikel`);
    } catch (error) {
      console.error("Google News scan error", error);
      setGoogleStatus("Fehler beim Google News Scan");
    } finally {
      setGoogleLoading(false);
    }
  }

  const googleByCategory = googleNews.reduce<Record<string, GoogleNewsItem[]>>((acc, item) => {
    const category = item.category || "general";
    if (!acc[category]) acc[category] = [];
    acc[category].push(item);
    return acc;
  }, {});

  async function runSignalScan() {
    setSignalLoading(true);
    setSignalStatus("Signal-Scan läuft...");
    try {
      const result = await api.runSignalScan();
      setSignals(result.signals || []);
      setSignalStatus(`Signal-Scan abgeschlossen – ${result.signals_found || 0} Signale`);
    } catch (error) {
      console.error("Signal scan error", error);
      setSignalStatus("Fehler beim Signal-Scan");
    } finally {
      setSignalLoading(false);
    }
  }

  const loadNews = useCallback(async (invalidate = false) => {
    if (invalidate) {
      cacheInvalidate('news:bullets');
      setRefreshing(true);
    }
    setLoading(!invalidate && news.length === 0);
    try {
      const { data: wl } = await cachedFetch("news:watchlist", () => api.getWatchlist(), 300);
      const allNews: NewsBullet[] = [];

      for (const item of wl || []) {
        try {
          const { data } = await cachedFetch(`news:memory:${item.ticker}`, () => api.getNewsMemory(item.ticker), 120);
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
      
      setDataAge(cacheAge("news:watchlist"));
      setFromCache(cacheAge("news:watchlist") !== null);
    } catch (error) {
      console.error("News load error", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [news.length]);

  async function runNewsScan() {
    setLoading(true);
    setScanResult("News-Scan läuft...");
    try {
      const result = await api.runNewsScan();
      setScanResult(`News-Scan abgeschlossen. ${result.results?.length || 0} Ticker gescannt.`);
      cacheInvalidateAll(); // Invalidates memory and bullets
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
      cacheInvalidateAll();
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
      cacheInvalidateAll();
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

  const signalColor = (type: string) => {
    if (type.includes("rsi")) return "bg-sky-500/10 text-sky-200 border border-sky-500/30";
    if (type.includes("volume")) return "bg-orange-500/10 text-orange-200 border border-orange-500/30";
    if (type.includes("sma")) return "bg-emerald-500/10 text-emerald-200 border border-emerald-500/30";
    if (type.includes("torpedo")) return "bg-rose-500/10 text-rose-200 border border-rose-500/30";
    if (type.includes("large")) return "bg-purple-500/10 text-purple-200 border border-purple-500/30";
    return "bg-[var(--bg-tertiary)] text-[var(--text-primary)] border border-[var(--border)]";
  };

  useEffect(() => {
    if (activeTab === "signals" && signals.length === 0 && !signalLoading) {
      runSignalScan();
    }
    if (activeTab === "google" && googleNews.length === 0 && !googleLoading) {
      runGoogleNewsScan();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  return (
    <div className="flex h-full gap-6">

      {/* ── LINKE SPALTE: Filter + Scans ──────────────────── */}
      <aside className="w-[220px] shrink-0 space-y-4">

        {/* Filter-Karte */}
        <div className="card p-4 space-y-4">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                        text-[var(--text-muted)]">Filter</p>

          {/* Ticker */}
          <div className="space-y-1.5">
            <label className="text-xs text-[var(--text-secondary)]">Ticker</label>
            <select
              value={filterTicker}
              onChange={(e) => setFilterTicker(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)]
                         bg-[var(--bg-tertiary)] px-3 py-1.5 text-xs
                         text-[var(--text-primary)] outline-none"
            >
              <option value="">Alle</option>
              {watchlist.map((w: any, idx: number) => (
                <option key={`${w.ticker}-${idx}`} value={w.ticker}>{w.ticker}</option>
              ))}
            </select>
          </div>

          {/* Sentiment */}
          <div className="space-y-1">
            <label className="text-xs text-[var(--text-secondary)]">Sentiment</label>
            {(["all", "positive", "negative"] as const).map((val) => (
              <button
                key={val}
                onClick={() => setFilterSentiment(val)}
                className={`w-full rounded-lg px-3 py-1.5 text-left text-xs
                             transition-colors ${
                  filterSentiment === val
                    ? "bg-[var(--accent-blue)]/15 text-[var(--accent-blue)]"
                    : "text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]"
                }`}
              >
                {val === "all" ? "Alle" : val === "positive" ? "↑ Positiv" : "↓ Negativ"}
              </button>
            ))}
          </div>

          {/* Material Toggle */}
          <label className="flex cursor-pointer items-center gap-2">
            <div
              onClick={() => setFilterMaterial(!filterMaterial)}
              className={`relative h-5 w-9 rounded-full transition-colors ${
                filterMaterial ? "bg-[var(--accent-blue)]" : "bg-[var(--bg-elevated)]"
              }`}
            >
              <div className={`absolute top-0.5 h-4 w-4 rounded-full bg-white
                               shadow transition-transform ${
                filterMaterial ? "translate-x-4" : "translate-x-0.5"
              }`} />
            </div>
            <span className="text-xs text-[var(--text-secondary)]">
              Nur Torpedo
            </span>
          </label>
        </div>

        {/* Scans-Karte */}
        <div className="card p-4 space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                        text-[var(--text-muted)] mb-3">Scans</p>

          {[
            { label: "News-Scan",    action: runNewsScan,       color: "bg-[var(--accent-blue)]",   loading: loading },
            { label: "SEC EDGAR",    action: runSecScan,        color: "bg-[var(--accent-amber)]",  loading: false   },
            { label: "Google News",  action: runGoogleNewsScan, color: "bg-[var(--accent-green)]",  loading: googleLoading },
            { label: "Makro",        action: runMacroScan,      color: "bg-[var(--accent-purple)]", loading: false   },
            { label: "Signale",      action: runSignalScan,     color: "bg-[var(--accent-red)]",    loading: signalLoading },
          ].map(({ label, action, color, loading: isLoading }) => (
            <button
              key={label}
              onClick={action}
              disabled={isLoading}
              className={`flex w-full items-center justify-between rounded-lg
                          px-3 py-2 text-xs font-medium text-white
                          transition-all hover:opacity-85 disabled:opacity-40 ${color}`}
            >
              <span>{label}</span>
              {isLoading
                ? <div className="h-3 w-3 animate-spin rounded-full border
                                  border-white/30 border-t-white" />
                : <Play size={11} />
              }
            </button>
          ))}

          {scanResult && (
            <p className="mt-2 text-[10px] text-[var(--text-muted)]">{scanResult}</p>
          )}
        </div>

        <CacheStatus
          fromCache={fromCache}
          ageSeconds={dataAge}
          onRefresh={() => loadNews(true)}
          refreshing={refreshing}
        />
      </aside>

      {/* ── RECHTE SPALTE: Feed ───────────────────────────── */}
      <main className="flex-1 min-w-0 space-y-4 overflow-y-auto
                       max-h-[calc(100vh-120px)]">

        {/* Seiten-Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">
              News-Feed
            </h1>
            <p className="text-xs text-[var(--text-secondary)]">
              {filtered.length} Einträge
              {filterTicker && ` · ${filterTicker}`}
              {filterMaterial && " · Nur Torpedo"}
            </p>
          </div>
        </div>

        {/* News-Stichpunkte */}
        {loading ? (
          <div className="space-y-3">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="h-3 w-16 rounded bg-[var(--bg-elevated)] mb-2" />
                <div className="h-4 w-full rounded bg-[var(--bg-elevated)]" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-8 text-center">
            <p className="text-sm text-[var(--text-muted)]">
              Keine News gefunden.{" "}
              <button
                onClick={runNewsScan}
                className="text-[var(--accent-blue)] underline hover:no-underline"
              >
                News-Scan starten
              </button>
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((item, idx) => (
              <div
                key={item.id || idx}
                className={`card px-4 py-3 ${
                  item.is_material
                    ? "border-l-2 border-l-[var(--accent-red)]"
                    : (item.sentiment_score ?? 0) > 0.3
                    ? "border-l-2 border-l-[var(--accent-green)]"
                    : (item.sentiment_score ?? 0) < -0.3
                    ? "border-l-2 border-l-[var(--accent-amber)]"
                    : ""
                }`}
              >
                {/* Zeile 1: Meta */}
                <div className="flex items-center gap-2 mb-1.5">
                  {item.is_material && (
                    <span className="badge badge-danger text-[9px] px-1.5 py-0.5">
                      ⚠ TORPEDO
                    </span>
                  )}
                  <span className="badge badge-neutral text-[9px] px-1.5 py-0.5">
                    {item.ticker}
                  </span>
                  {item.category && (
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {item.category}
                    </span>
                  )}
                  <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                    {item.created_at
                      ? new Date(item.created_at).toLocaleDateString("de-DE", {
                          day: "2-digit", month: "short",
                        })
                      : "—"}
                  </span>
                  {/* Sentiment-Zahl */}
                  <span className={`text-[10px] font-mono font-semibold ${
                    (item.sentiment_score ?? 0) > 0.3
                      ? "text-[var(--accent-green)]"
                      : (item.sentiment_score ?? 0) < -0.3
                      ? "text-[var(--accent-red)]"
                      : "text-[var(--text-muted)]"
                  }`}>
                    {item.sentiment_score !== undefined
                      ? (item.sentiment_score > 0 ? "+" : "") +
                        item.sentiment_score.toFixed(2)
                      : "—"}
                  </span>
                </div>

                {/* Zeile 2: Text */}
                <p className="text-sm text-[var(--text-primary)] leading-relaxed">
                  {item.bullet_text}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* ── Google News (immer sichtbar wenn Daten vorhanden) ── */}
        {googleNews.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                          text-[var(--text-muted)] mt-6 mb-3">
              🌐 Google News ({googleNews.length})
            </p>
            <div className="space-y-2">
              {googleNews.slice(0, 15).map((item, idx) => (
                <div key={idx}
                     className="card px-4 py-3 border-l-2 border-l-blue-500/40">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] text-[var(--text-muted)]">
                      {item.source}
                    </span>
                    {item.related_ticker && (
                      <span className="badge badge-neutral text-[9px] px-1.5 py-0.5">
                        {item.related_ticker}
                      </span>
                    )}
                    {item.sentiment_score !== undefined && (
                      <span className={`ml-auto text-[10px] font-mono font-semibold ${
                        item.sentiment_score > 0.2
                          ? "text-[var(--accent-green)]"
                          : item.sentiment_score < -0.2
                          ? "text-[var(--accent-red)]"
                          : "text-[var(--text-muted)]"
                      }`}>
                        {item.sentiment_score > 0 ? "+" : ""}
                        {item.sentiment_score.toFixed(2)}
                      </span>
                    )}
                  </div>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm text-[var(--text-primary)] hover:text-[var(--accent-blue)]
                               leading-relaxed transition-colors"
                  >
                    {item.headline}
                  </a>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Signale (immer sichtbar wenn Daten vorhanden) ── */}
        {signals.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.25em]
                          text-[var(--text-muted)] mt-6 mb-3">
              ⚡ Signale ({signals.length})
            </p>
            <div className="grid gap-2 sm:grid-cols-2">
              {signals.map((signal, idx) => (
                <div
                  key={`${signal.ticker}-${idx}`}
                  className={`rounded-xl p-4 ${signalColor(signal.type)}`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono font-bold text-white">
                      {signal.ticker}
                    </span>
                    <span className="text-[10px] text-white/70 uppercase">
                      {signal.type}
                    </span>
                  </div>
                  <p className="text-xs text-white/90 leading-relaxed">
                    {signal.alert_text}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Leerer Gesamt-State */}
        {!loading && filtered.length === 0 &&
         googleNews.length === 0 && signals.length === 0 && (
          <div className="card p-12 text-center">
            <p className="text-sm text-[var(--text-muted)] mb-3">
              Noch keine Daten. Starte einen Scan in der linken Spalte.
            </p>
          </div>
        )}

      </main>
    </div>
  );
}

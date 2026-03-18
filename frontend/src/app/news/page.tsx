"use client";

import { useState, useEffect } from "react";
import { Newspaper, Play, Filter, Circle, Activity, Radar, Sparkles } from "lucide-react";
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

type SignalItem = {
  ticker: string;
  type: string;
  alert_text: string;
};

export default function NewsPage() {
  const [news, setNews] = useState<NewsBullet[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterTicker, setFilterTicker] = useState("");
  const [filterSentiment, setFilterSentiment] = useState<"all" | "positive" | "negative">("all");
  const [filterMaterial, setFilterMaterial] = useState(false);
  const [scanResult, setScanResult] = useState("");
  const [watchlist, setWatchlist] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"news" | "signals">("news");
  const [signals, setSignals] = useState<SignalItem[]>([]);
  const [signalStatus, setSignalStatus] = useState<string>("");
  const [signalLoading, setSignalLoading] = useState(false);

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  return (
    <div className="space-y-8 p-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-4xl font-bold text-[var(--text-primary)]">Signal Intelligence</h1>
          <p className="text-sm text-[var(--text-secondary)] mt-2">News & technische Signale in Echtzeit</p>
        </div>
        <div className="inline-flex rounded-full border border-[var(--border)] bg-[var(--bg-secondary)] p-1 text-sm">
          <button
            onClick={() => setActiveTab("news")}
            className={`flex items-center gap-2 rounded-full px-4 py-1 ${
              activeTab === "news" ? "bg-[var(--accent-blue)] text-white" : "text-[var(--text-secondary)]"
            }`}
          >
            <Newspaper size={14} /> News
          </button>
          <button
            onClick={() => setActiveTab("signals")}
            className={`flex items-center gap-2 rounded-full px-4 py-1 ${
              activeTab === "signals" ? "bg-[var(--accent-purple)] text-white" : "text-[var(--text-secondary)]"
            }`}
          >
            <Radar size={14} /> Signale
          </button>
        </div>
      </div>

      {activeTab === "news" ? (
        <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
          <div className="space-y-6">
            <div className="card p-5">
              <div className="flex flex-wrap items-center gap-3">
                <Filter size={18} className="text-[var(--text-muted)]" />
                <select
                  value={filterTicker}
                  onChange={(e) => setFilterTicker(e.target.value)}
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none shadow-sm"
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
                  className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none shadow-sm"
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
                    className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent-blue)]"
                  />
                  Nur Material Events
                </label>
              </div>
            </div>

            <div className="max-h-[700px] space-y-4 overflow-y-auto">
              {loading ? (
                <div className="card p-6 text-center">
                  <p className="text-sm text-[var(--text-muted)]">Lade News...</p>
                </div>
              ) : filtered.length === 0 ? (
                <div className="card p-6 text-center">
                  <p className="text-sm text-[var(--text-muted)]">Keine News gefunden.</p>
                </div>
              ) : (
                filtered.map((item, idx) => (
                  <div
                    key={item.id || idx}
                    className={`card p-5 ${
                      item.is_material ? "border-l-4 border-l-[var(--accent-red)]" : ""
                    }`}
                  >
                    <div className="flex items-start gap-4">
                      <Circle
                        size={8}
                        className={`mt-2 flex-shrink-0 ${
                          (item.sentiment_score ?? 0) > 0.3
                            ? "fill-[var(--accent-green)] text-[var(--accent-green)]"
                            : (item.sentiment_score ?? 0) < -0.3
                            ? "fill-[var(--accent-red)] text-[var(--accent-red)]"
                            : "fill-[var(--text-muted)] text-[var(--text-muted)]"
                        }`}
                      />
                      <div className="flex-1">
                        <div className="mb-2 flex items-center gap-2">
                          <span className="badge badge-neutral">{item.ticker}</span>
                          <span className="badge badge-info">{item.category || "News"}</span>
                          {item.is_material && (
                            <span className="badge badge-danger">TORPEDO</span>
                          )}
                          <span className="ml-auto text-xs text-[var(--text-muted)]">
                            {item.created_at ? new Date(item.created_at).toLocaleString("de-DE") : "-"}
                          </span>
                        </div>
                        <p className="text-sm text-[var(--text-primary)] leading-relaxed">{item.bullet_text}</p>
                        <div className="mt-2 flex items-center gap-2">
                          <span className="text-xs text-[var(--text-muted)]">Sentiment:</span>
                          <span
                            className={`text-sm font-bold ${
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
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="space-y-6">
            <div className="card p-6">
              <h2 className="text-lg font-bold text-[var(--text-primary)] mb-4">Scan Actions</h2>
              <div className="space-y-3">
                <button
                  onClick={runNewsScan}
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
                >
                  <Play size={18} />
                  News Scan
                </button>
                <button
                  onClick={runSecScan}
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-amber)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
                >
                  <Play size={18} />
                  SEC Scan
                </button>
                <button
                  onClick={runMacroScan}
                  disabled={loading}
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-purple)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
                >
                  <Play size={18} />
                  Macro Scan
                </button>
              </div>
              {scanResult && (
                <div className="mt-4 rounded-lg bg-[var(--bg-tertiary)] p-4 text-sm text-[var(--text-primary)]">
                  {scanResult}
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-[var(--text-primary)]">Smart Alerts</h2>
                <p className="text-sm text-[var(--text-secondary)]">RSI, Volumen, SMA & Score-basierte Signale</p>
              </div>
              <button
                onClick={runSignalScan}
                disabled={signalLoading}
                className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent-green)] px-4 py-2 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
              >
                {signalLoading ? <Activity size={16} className="animate-spin" /> : <Sparkles size={16} />} 
                {signalLoading ? "Scan läuft..." : "Signal-Scan jetzt"}
              </button>
            </div>
            {signalStatus && (
              <div className="mt-3 rounded-lg bg-[var(--bg-tertiary)] p-3 text-sm text-[var(--text-primary)]">
                {signalStatus}
              </div>
            )}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            {signals.length === 0 ? (
              <div className="card p-6 text-center text-sm text-[var(--text-muted)]">
                Noch keine Signale – starte einen Scan.
              </div>
            ) : (
              signals.map((signal, idx) => (
                <div key={`${signal.ticker}-${idx}`} className={`rounded-2xl p-5 ${signalColor(signal.type)}`}>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-[0.2em] text-[var(--text-muted)]">{signal.type}</p>
                      <p className="text-2xl font-bold text-white">{signal.ticker}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-white whitespace-pre-line">{signal.alert_text}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

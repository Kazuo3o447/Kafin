"use client";

import { useState, useEffect } from "react";
import { Play, CheckCircle, XCircle, AlertTriangle, Database, Plus, Trash2, Activity, Clock, Download, RefreshCw, Send, BarChart3, Settings, Globe, Zap, Calendar, Search } from "lucide-react";
import { api } from "@/lib/api";

// Types
type DiagnosticResult = {
  supabase?: { status: string; details?: string };
  deepseek?: { status: string; details?: string };
  finnhub?: { status: string; details?: string };
  fmp?: { status: string; details?: string };
  fred?: { status: string; details?: string };
  finbert?: { status: string; details?: string };
  telegram?: { status: string; details?: string };
  n8n?: { status: string; details?: string };
};

type DbStatus = {
  status?: string;
  tables?: Record<string, { count: number | string; status?: string }>;
  message?: string;
};

type SearchTerm = {
  id?: string;
  term: string;
  category?: string;
  is_active?: boolean;
  created_at?: string;
};

type ModuleStatus = {
  label: string;
  status: "ok" | "warning" | "error" | "unknown";
  last_run?: string;
  last_run_relative?: string;
  last_error?: { timestamp: string; level: string; event: string } | null;
  stats?: string;
  recent_logs?: any[];
};

type ModuleStatusResponse = {
  modules: Record<string, ModuleStatus>;
  generated_at?: string;
  timestamp?: string;
};

type LogStats = {
  stats?: {
    total: number;
    error: number;
    warning: number;
    info: number;
    ignore?: number;
  };
  recent_errors: string[];
  recent_warnings?: string[];
};

type LogEntry = {
  timestamp: string;
  level: string;
  logger: string;
  event: string;
};

type ActionResult = {
  action: string;
  success: boolean;
  message: string;
  timestamp: Date;
};

type ScoringConfig = {
  opportunity_score: Record<string, number>;
  torpedo_score: Record<string, number>;
  thresholds?: Record<string, number>;
};

type WatchlistItem = {
  ticker: string;
  company_name?: string;
};

type NewsMemory = {
  count: number;
  last_date?: string;
  latest_bullet?: string;
};

type TabId = "uebersicht" | "pipeline" | "apis" | "daten" | "konfiguration";

export default function SettingsPage() {
  // Tab state
  const [activeTab, setActiveTab] = useState<TabId>("uebersicht");
  
  // Übersicht state
  const [moduleStatus, setModuleStatus] = useState<ModuleStatusResponse | null>(null);
  const [logStats, setLogStats] = useState<LogStats | null>(null);
  const [errorLogs, setErrorLogs] = useState<LogEntry[]>([]);
  const [lastSystemCheck, setLastSystemCheck] = useState<Date | null>(null);
  
  // Pipeline state
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [actionResults, setActionResults] = useState<ActionResult[]>([]);
  
  // APIs state
  const [apiDiagnostics, setApiDiagnostics] = useState<DiagnosticResult>({});
  const [finbertTestText, setFinbertTestText] = useState("");
  const [finbertResult, setFinbertResult] = useState<{ score: number; label: string } | null>(null);
  
  // Daten state
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [selectedTicker, setSelectedTicker] = useState<string>("");
  const [newsMemory, setNewsMemory] = useState<NewsMemory | null>(null);
  const [scoringConfig, setScoringConfig] = useState<ScoringConfig | null>(null);
  
  // Existing state (preserve for compatibility)
  const [diagnostics, setDiagnostics] = useState<DiagnosticResult>({});
  const [dbStatus, setDbStatus] = useState<DbStatus>({});
  const [loading, setLoading] = useState(false);
  const [termsLoading, setTermsLoading] = useState(false);
  const [searchTerms, setSearchTerms] = useState<SearchTerm[]>([]);
  const [newTerm, setNewTerm] = useState("");
  const [newCategory, setNewCategory] = useState("macro");
  const [expandedModules, setExpandedModules] = useState<Record<string, string[]>>({});
  const [termAction, setTermAction] = useState<string | null>(null);

  // Tab navigation
  const tabs = [
    { id: "uebersicht" as TabId, label: "Übersicht", icon: Activity },
    { id: "pipeline" as TabId, label: "Pipeline", icon: Zap },
    { id: "apis" as TabId, label: "APIs", icon: Globe },
    { id: "daten" as TabId, label: "Daten", icon: Database },
    { id: "konfiguration" as TabId, label: "Konfiguration", icon: Settings },
  ];

  // API functions for Übersicht
  async function loadModuleStatus() {
    try {
      const response = await fetch("/api/logs/module-status");
      const data = await response.json();
      setModuleStatus(data);
    } catch (error) {
      console.error("Module status error", error);
    }
  }

  async function loadLogStats() {
    try {
      const response = await fetch("/api/logs/stats");
      const data = await response.json();
      setLogStats(data);
    } catch (error) {
      console.error("Log stats error", error);
    }
  }

  async function loadErrorLogs() {
    try {
      const response = await fetch("/api/logs/errors");
      const data = await response.json();
      setErrorLogs(data.errors || []);
    } catch (error) {
      console.error("Error logs error", error);
    }
  }

  async function runFullSystemCheck() {
    setLoading(true);
    try {
      const response = await fetch("/api/diagnostics/full", { method: "POST" });
      const data = await response.json();
      setApiDiagnostics(data.details || data.services || {});
      setLastSystemCheck(new Date());
      localStorage.setItem("lastSystemCheck", new Date().toISOString());
    } catch (error) {
      console.error("System check error", error);
    } finally {
      setLoading(false);
    }
  }

  async function exportLogs() {
    try {
      const response = await fetch("/api/logs/export");
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `kafin-logs-${new Date().toISOString().split("T")[0]}.log`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Export logs error", error);
    }
  }

  async function clearLogs() {
    if (!window.confirm("Alle Logs unwiderruflich löschen?")) return;
    try {
      await fetch("/api/logs/file", { method: "DELETE" });
      await loadLogStats();
      await loadErrorLogs();
    } catch (error) {
      console.error("Clear logs error", error);
    }
  }

  // Pipeline functions
  async function executeAction(actionId: string, apiCall: () => Promise<any>) {
    setLoadingAction(actionId);
    try {
      const response = await apiCall();
      const data = await response.json?.() || {};
      
      // Smarte Zusammenfassung je nach Endpoint
      let summary = "Abgeschlossen";
      if (data.results && Array.isArray(data.results)) {
        const total = data.results.length;
        const material = data.results.filter((r: any) => r.alerts_sent > 0).length;
        summary = `${total} Ticker gescannt${material > 0 ? `, ${material} Alerts` : ""}`;
      } else if (data.processed !== undefined) {
        summary = `${data.processed} verarbeitet`;
      } else if (data.status === "success") {
        summary = data.message || "Erfolgreich";
      } else if (data.count !== undefined) {
        summary = `${data.count} Einträge`;
      } else if (!response.ok) {
        summary = `Fehler ${response.status}`;
      }
      
      const actionResult: ActionResult = {
        action: actionId,
        success: response.ok,
        message: summary,
        timestamp: new Date(),
      };
      setActionResults(prev => [actionResult, ...prev.slice(0, 4)]);
    } catch (error) {
      const actionResult: ActionResult = {
        action: actionId,
        success: false,
        message: error instanceof Error ? error.message : "Unbekannter Fehler",
        timestamp: new Date(),
      };
      setActionResults(prev => [actionResult, ...prev.slice(0, 4)]);
    } finally {
      setLoadingAction(null);
    }
  }

  // API functions
  async function testFinbert() {
    if (!finbertTestText.trim()) return;
    setLoadingAction("finbert-test");
    try {
      const response = await fetch(`/api/finbert/analyze?text=${encodeURIComponent(finbertTestText)}`, {
        method: "POST",
      });
      const data = await response.json();
      const score = data.sentiment_score;
      const label = score > 0.15 ? "Bullish" : score < -0.15 ? "Bearish" : "Neutral";
      setFinbertResult({ score, label });
    } catch (error) {
      console.error("FinBERT test error", error);
    } finally {
      setLoadingAction(null);
    }
  }

  // Daten functions
  async function loadWatchlist() {
    try {
      const result = await api.getWatchlist();
      setWatchlist(result || []);
    } catch (error) {
      console.error("Watchlist load error", error);
    }
  }

  async function loadNewsMemory(ticker: string) {
    try {
      const response = await fetch(`/api/news/memory/${ticker}`);
      const data = await response.json();
      setNewsMemory({
        count: data.count || 0,
        last_date: data.bullet_points?.[0]?.date,
        latest_bullet: data.bullet_points?.[0]?.bullet_points?.[0],
      });
    } catch (error) {
      console.error("News memory error", error);
    }
  }

  async function loadScoringConfig() {
    try {
      const response = await fetch("/api/data/scoring-config");
      const data = await response.json();
      setScoringConfig(data);
    } catch (error) {
      console.error("Scoring config error", error);
    }
  }

  // Effects
  useEffect(() => {
    // Load last system check from localStorage
    const saved = localStorage.getItem("lastSystemCheck");
    if (saved) {
      setLastSystemCheck(new Date(saved));
    }
  }, []);

  useEffect(() => {
    if (activeTab === "uebersicht") {
      loadModuleStatus();
      loadLogStats();
      loadErrorLogs();
      const interval = setInterval(() => {
        loadModuleStatus();
        loadLogStats();
        loadErrorLogs();
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  useEffect(() => {
    if (activeTab === "daten") {
      loadWatchlist();
      loadScoringConfig();
    }
  }, [activeTab]);

  useEffect(() => {
    loadSearchTerms();
  }, []);

  // Helper functions
  function getStatusIcon(status?: string) {
    if (status === "ok" || status === "success") return <CheckCircle size={20} className="text-[var(--accent-green)]" />;
    if (status === "warning") return <AlertTriangle size={20} className="text-[var(--accent-amber)]" />;
    return <XCircle size={20} className="text-[var(--accent-red)]" />;
  }

  function getTimeDelta(timestamp: string) {
    const now = new Date();
    const then = new Date(timestamp);
    const diffMs = now.getTime() - then.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `vor ${diffMins} Min`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `vor ${diffHours} Std`;
    return `vor ${Math.floor(diffHours / 24)} Tagen`;
  }

  function getSystemStatus() {
    const modules = Object.values(moduleStatus?.modules || {});
    const hasErrors = modules.some((m: ModuleStatus) => m.status === "error");
    const hasWarnings = modules.some((m: ModuleStatus) => m.status === "warning");
    if (hasErrors) return { status: "degraded", color: "text-[var(--accent-red)]", text: "⚠ Degraded" };
    if (hasWarnings) return { status: "degraded", color: "text-[var(--accent-amber)]", text: "⚠ Degraded" };
    return { status: "ok", color: "text-[var(--accent-green)]", text: "● Kafin läuft" };
  }

  // Existing functions (preserve for compatibility)
  async function loadSearchTerms() {
    setTermsLoading(true);
    try {
      const result = await api.getSearchTerms();
      setSearchTerms(result.terms || []);
    } catch (error) {
      console.error("Search terms load error", error);
    } finally {
      setTermsLoading(false);
    }
  }

  async function handleAddTerm() {
    if (!newTerm.trim()) return;
    setTermAction("add");
    try {
      await api.addSearchTerm(newTerm.trim(), newCategory);
      setNewTerm("");
      await loadSearchTerms();
    } catch (error) {
      alert("Fehler beim Hinzufügen des Suchbegriffs.");
    } finally {
      setTermAction(null);
    }
  }

  async function handleRemoveTerm(term: string) {
    setTermAction(term);
    try {
      await api.removeSearchTerm(term);
      await loadSearchTerms();
    } catch (error) {
      alert("Fehler beim Entfernen des Suchbegriffs.");
    } finally {
      setTermAction(null);
    }
  }

  async function runDiagnostics() {
    setLoading(true);
    setDiagnostics({});
    
    try {
      const startTime = Date.now();
      const result = await api.getDiagnostics();
      const endTime = Date.now();
      const latency = endTime - startTime;
      
      // Füge Latenz zu jedem Service hinzu
      const resultsWithLatency = { ...(result.details || result.services || {}) };
      Object.keys(resultsWithLatency).forEach(key => {
        if (resultsWithLatency[key]) {
          resultsWithLatency[key] = {
            ...resultsWithLatency[key],
            latency: `${latency}ms`
          };
        }
      });
      
      setDiagnostics(resultsWithLatency);
    } catch (error) {
      console.error("Diagnostics error", error);
      // Bei Fehler alle Services als fehlgeschlagen markieren
      setDiagnostics({
        supabase: { status: "error", details: "Nicht getestet" },
        deepseek: { status: "error", details: "Nicht getestet" },
        finnhub: { status: "error", details: "Nicht getestet" },
        fmp: { status: "error", details: "Nicht getestet" },
        fred: { status: "error", details: "Nicht getestet" },
        finbert: { status: "error", details: "Nicht getestet" },
        telegram: { status: "error", details: "Nicht getestet" },
        n8n: { status: "error", details: "Nicht getestet" }
      });
    } finally {
      setLoading(false);
    }
  }

  async function loadDbStatus() {
    setLoading(true);
    try {
      const result = await api.getDbStatus();
      setDbStatus(result);
    } catch (error) {
      console.error("DB status error", error);
    } finally {
      setLoading(false);
    }
  }

  async function testTelegram() {
    setLoading(true);
    try {
      await api.testTelegram();
      alert("Telegram-Test-Nachricht wurde gesendet.");
    } catch (error) {
      alert("Fehler beim Telegram-Test.");
    } finally {
      setLoading(false);
    }
  }

  async function setupN8n() {
    setLoading(true);
    try {
      await api.setupN8n();
      alert("n8n-Workflows wurden eingerichtet.");
    } catch (error) {
      alert("Fehler beim Einrichten der n8n-Workflows.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-4xl font-bold text-[var(--text-primary)]">Einstellungen</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">Command Center – System-Status, Pipeline-Steuerung & Konfiguration</p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-[var(--border)]">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? "border-[var(--accent-blue)] text-[var(--accent-blue)]"
                  : "border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              }`}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === "uebersicht" && (
        <div className="space-y-6">
          {/* Readiness Banner */}
          {(() => {
            const modules = Object.values(moduleStatus?.modules || {}) as ModuleStatus[];
            const okCount = modules.filter(m => m.status === "ok").length;
            const errorCount = logStats?.stats?.error ?? "—";
            const allOk = okCount === modules.length && modules.length > 0;
            const color = allOk ? "var(--accent-green)" : "var(--accent-amber)";
            const bg = allOk ? "rgba(34, 197, 94, 0.1)" : "rgba(245, 158, 11, 0.1)";
            return (
              <div style={{
                background: bg,
                border: `1px solid ${color}`,
                borderRadius: "10px",
                padding: "10px 16px",
                display: "flex",
                alignItems: "center",
                gap: "24px",
                flexWrap: "wrap",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                  <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: color }} />
                  <span style={{ fontSize: "12px", fontWeight: 600, color }}>
                    {allOk ? "Bereit" : "Prüfen erforderlich"}
                  </span>
                </div>
                <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                  Module: {okCount}/{modules.length} OK
                </span>
                <span style={{ fontSize: "11px", color: "var(--text-secondary)" }}>
                  Errors (24h): {errorCount}
                </span>
                {lastSystemCheck && (
                  <span style={{ fontSize: "11px", color: "var(--text-muted)", marginLeft: "auto" }}>
                    Letzter Check: {lastSystemCheck.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
            );
          })()}

          {/* System Header */}
          <div className="flex items-center justify-between py-4">
            <div>
              <div className={`text-lg font-bold ${getSystemStatus().color}`}>
                {getSystemStatus().text}
              </div>
              <div className="text-sm text-[var(--text-muted)]">
                Letzter Systemcheck: {lastSystemCheck ? getTimeDelta(lastSystemCheck.toISOString()) : "noch nicht"}
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={runFullSystemCheck}
                disabled={loading}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <Activity size={16} />
                {loading ? "Läuft..." : "Systemcheck starten"}
              </button>
              <button
                onClick={exportLogs}
                className="flex items-center gap-2 rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]"
              >
                <Download size={16} />
                Logs exportieren
              </button>
            </div>
          </div>

          {/* Module Status Grid */}
          {moduleStatus && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {Object.entries(moduleStatus.modules || {}).map(([id, module]) => (
                <div key={id} className="card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">{module.label}</h3>
                    {getStatusIcon(module.status)}
                  </div>
                  <div className="text-xs text-[var(--text-muted)] mb-2">
                    Zuletzt aktiv: {module.last_run_relative || "unbekannt"}
                  </div>
                  {module.stats && (
                    <div className="text-xs text-[var(--text-secondary)] mb-2">{module.stats}</div>
                  )}
                  <button
                    onClick={async () => {
                      try {
                        const res = await fetch(`/api/logs/module/${id}`);
                        const logs = await res.json();
                        setExpandedModules(prev => ({ ...prev, [id]: logs }));
                      } catch (e) {
                        console.error("Failed to load module logs", e);
                      }
                    }}
                    className="text-xs px-2 py-1 rounded border border-[var(--border)] hover:bg-[var(--bg-tertiary)]"
                  >
                    {expandedModules[id] ? "Logs verbergen" : "Logs anzeigen"}
                  </button>
                  {expandedModules[id] && (
                    <div className="mt-2 space-y-1 max-h-32 overflow-y-auto">
                      {expandedModules[id].slice(0, 5).map((log: any, idx: number) => (
                        <div key={idx} className="text-xs font-mono bg-[var(--bg-tertiary)] p-1 rounded truncate">
                          <span className={log.level === "error" ? "text-red-400" : log.level === "warning" ? "text-amber-400" : "text-[var(--text-secondary)]"}>
                            {log.timestamp?.slice(11, 19)}
                          </span>{" "}
                          {log.event?.slice(0, 60)}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Error Feed */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Fehler-Feed (letzte 24h)</h3>
            {errorLogs.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {errorLogs.map((log, idx) => (
                  <div key={idx} className="flex items-center gap-4 text-xs font-mono bg-[var(--bg-tertiary)] p-2 rounded">
                    <span className="text-[var(--text-muted)]">{log.timestamp}</span>
                    <span className={`px-2 py-1 rounded ${
                      log.level === "error" ? "bg-red-500/20 text-red-300" : "bg-amber-500/20 text-amber-300"
                    }`}>{log.level}</span>
                    <span className="text-[var(--text-secondary)]">{log.logger}</span>
                    <span className="text-[var(--text-primary)]">{log.event}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-[var(--text-muted)]">
                Keine Fehler in den letzten 24 Stunden ✓
              </div>
            )}
          </div>

          {/* Log Statistics */}
          {logStats && (
            <div className="card p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Log-Statistiken</h3>
                <button
                  onClick={clearLogs}
                  className="flex items-center gap-2 rounded-lg border border-[var(--accent-red)] px-3 py-1 text-xs text-[var(--accent-red)] hover:bg-red-500/10"
                >
                  <Trash2 size={14} />
                  Log-Datei löschen
                </button>
              </div>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-[var(--text-primary)]">{logStats.stats?.total ?? 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Gesamt-Logs</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-[var(--accent-red)]">{logStats.stats?.error ?? 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Errors</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-[var(--accent-amber)]">{logStats.stats?.warning ?? 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Warnings</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-[var(--accent-blue)]">{logStats.stats?.info ?? 0}</div>
                  <div className="text-xs text-[var(--text-muted)]">Info</div>
                </div>
              </div>
              {logStats.recent_errors && logStats.recent_errors.length > 0 && (
                <div>
                  <div className="text-sm font-medium text-[var(--text-primary)] mb-2">Letzte kritische Fehler:</div>
                  <div className="space-y-1">
                    {logStats.recent_errors.map((error, idx) => (
                      <div key={idx} className="text-xs text-[var(--text-secondary)] font-mono bg-[var(--bg-tertiary)] p-2 rounded">
                        {error}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === "pipeline" && (
        <div className="space-y-6">
          <div className="text-sm text-[var(--text-muted)]">
            Manuelles Triggern aller Pipelines. Ergebnisse erscheinen unter jedem Button.
          </div>

          {/* News Pipeline */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">News-Pipeline</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">
              Scannt Finnhub + Google News für alle Watchlist-Ticker. Automatisch alle 30 Min (Werktag).
            </p>
            <div className="text-xs text-[var(--text-muted)] mb-4 bg-[var(--bg-tertiary)] p-3 rounded">
              <strong>n8n-Zeitplan:</strong><br/>
              Werktag: Mo-Fr 13:00-22:30 Uhr, alle 30 Min<br/>
              Wochenende: Sa/So 10:00/14:00/18:00/22:00 Uhr
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <button
                onClick={() => executeAction("news-scan", () => fetch("/api/news/scan", { method: "POST" }))}
                disabled={loadingAction === "news-scan"}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw size={16} className={loadingAction === "news-scan" ? "animate-spin" : ""} />
                {loadingAction === "news-scan" ? "Läuft..." : "News-Scan (alle Ticker)"}
              </button>
              <button
                onClick={() => executeAction("google-news", () => fetch("/api/google-news/scan"))}
                disabled={loadingAction === "google-news"}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw size={16} className={loadingAction === "google-news" ? "animate-spin" : ""} />
                {loadingAction === "google-news" ? "Läuft..." : "Google News Scan"}
              </button>
              <button
                onClick={() => executeAction("macro-scan", () => fetch("/api/news/macro-scan", { method: "POST" }))}
                disabled={loadingAction === "macro-scan"}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw size={16} className={loadingAction === "macro-scan" ? "animate-spin" : ""} />
                {loadingAction === "macro-scan" ? "Läuft..." : "Makro-Scan (GENERAL_MACRO)"}
              </button>
              <button
                onClick={() => executeAction("sec-scan", () => fetch("/api/news/sec-scan", { method: "POST" }))}
                disabled={loadingAction === "sec-scan"}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <RefreshCw size={16} className={loadingAction === "sec-scan" ? "animate-spin" : ""} />
                {loadingAction === "sec-scan" ? "Läuft..." : "SEC EDGAR Scan"}
              </button>
            </div>
          </div>

          {/* Action Results */}
          {actionResults.length > 0 && (
            <div className="card p-6">
              <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Letzte Aktionen</h3>
              <div className="space-y-2">
                {actionResults.map((result, idx) => (
                  <div key={idx} className={`flex items-center justify-between p-3 rounded ${
                    result.success ? "bg-green-500/10" : "bg-red-500/10"
                  }`}>
                    <div className="flex items-center gap-3">
                      {result.success ? <CheckCircle size={16} className="text-green-500" /> : <XCircle size={16} className="text-red-500" />}
                      <span className="text-sm font-medium text-[var(--text-primary)]">{result.action}</span>
                    </div>
                    <div className="text-xs text-[var(--text-secondary)]">
                      {result.timestamp.toLocaleTimeString("de-DE")}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === "apis" && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-[var(--text-primary)]">API-Diagnostics</h2>
              <p className="text-sm text-[var(--text-secondary)] mt-1">
                Systemcheck dauert ~15-30 Sekunden und macht echte API-Calls.
              </p>
            </div>
            <button
              onClick={runFullSystemCheck}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              <Play size={16} />
              {loading ? "Läuft..." : "Systemcheck starten"}
            </button>
          </div>

          {/* API Status Grid */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {[
              { key: "supabase", label: "Supabase" },
              { key: "deepseek", label: "DeepSeek" },
              { key: "finnhub", label: "Finnhub" },
              { key: "fmp", label: "FMP" },
              { key: "fred", label: "FRED" },
              { key: "finbert", label: "FinBERT" },
              { key: "telegram", label: "Telegram" },
              { key: "n8n", label: "n8n" },
            ].map(({ key, label }) => {
              const status = apiDiagnostics[key as keyof DiagnosticResult];
              return (
                <div key={key} className="card p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-sm font-bold text-[var(--text-primary)]">{label}</h3>
                    {getStatusIcon(status?.status)}
                  </div>
                  <p className="text-xs text-[var(--text-muted)] leading-relaxed">{status?.details || "Not tested yet"}</p>
                  {lastSystemCheck && (
                    <p className="text-xs text-[var(--text-muted)] mt-2">
                      Getestet: {getTimeDelta(lastSystemCheck.toISOString())}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* FinBERT Test */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">FinBERT Test</h3>
            <div className="flex gap-3 mb-4">
              <input
                value={finbertTestText}
                onChange={(e) => setFinbertTestText(e.target.value)}
                placeholder="Text für Sentiment-Analyse..."
                className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
              />
              <button
                onClick={testFinbert}
                disabled={loadingAction === "finbert-test" || !finbertTestText.trim()}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <BarChart3 size={16} />
                {loadingAction === "finbert-test" ? "Analysiere..." : "FinBERT testen"}
              </button>
            </div>
            {finbertResult && (
              <div className="text-sm text-[var(--text-secondary)]">
                Score: <span className="font-bold text-[var(--text-primary)]">{finbertResult.score.toFixed(3)}</span> | 
                Label: <span className="font-bold text-[var(--text-primary)]">{finbertResult.label}</span>
              </div>
            )}
          </div>

          {/* Telegram Test */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Telegram Live-Test</h3>
            <button
              onClick={() => executeAction("telegram-test", () => fetch("/api/telegram/test", { method: "POST" }))}
              disabled={loadingAction === "telegram-test"}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
            >
              <Send size={16} />
              {loadingAction === "telegram-test" ? "Sende..." : "Test-Nachricht senden"}
            </button>
            {actionResults.find(r => r.action === "telegram-test") && (
              <p className="text-sm text-[var(--text-secondary)] mt-2">
                ✓ Nachricht gesendet — prüfe Telegram
              </p>
            )}
          </div>
        </div>
      )}

      {activeTab === "daten" && (
        <div className="space-y-6">
          {/* DB Status */}
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-[var(--text-primary)]">Datenbank-Status</h3>
              <button
                onClick={() => executeAction("db-status", async () => {
                    const res = await fetch("/api/diagnostics/db");
                    const data = await res.json();
                    setDbStatus(data);
                    return data;
                  })}
                disabled={loadingAction === "db-status"}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <Database size={16} />
                {loadingAction === "db-status" ? "Lade..." : "DB-Status laden"}
              </button>
            </div>
            {dbStatus.tables && (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b border-[var(--border)]">
                    <tr>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Table Name</th>
                      <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Row Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(dbStatus.tables || {}).map(([tableName, tableData]) => (
                      <tr key={tableName} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                        <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{tableName}</td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">{typeof tableData.count === 'number' ? tableData.count.toLocaleString() : tableData.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Custom Search Terms */}
          <div className="card p-6">
            <div className="mb-6">
              <h3 className="text-lg font-bold text-[var(--text-primary)] mb-2">Google News — Custom Suchbegriffe</h3>
              <div className="text-sm text-[var(--text-secondary)] bg-[var(--bg-tertiary)] p-4 rounded mb-4">
                <p className="font-bold mb-2">Wie funktioniert der News-Filter?</p>
                <p className="mb-2"><strong>Automatisch:</strong> Alle Watchlist-Ticker werden automatisch als Suchbegriffe genutzt — du musst NVDA nicht manuell hinzufügen.</p>
                <p className="mb-2"><strong>Problem:</strong> Konkurrenz-Meldungen werden NICHT automatisch erkannt. Wenn Novo Nordisk eine Entscheidung zu GLP-1 trifft die HIMS betrifft, erscheint diese Meldung nur wenn du 'GLP-1' oder 'semaglutide' als Custom-Begriff hinzufügst.</p>
                <p><strong>Tipp:</strong> Füge Produkt-Namen, Wirkstoffe, Konkurrenten und Branchen-Keywords hinzu — nicht nur Ticker.</p>
              </div>
            </div>

            {/* Automatic Terms */}
            <div className="mb-4 p-4 bg-[var(--bg-tertiary)] rounded">
              <div className="text-sm font-medium text-[var(--text-primary)] mb-2">Automatische Terme (aus Watchlist):</div>
              <div className="text-sm text-[var(--text-secondary)]">
                {watchlist.map(item => item.ticker).join(" · ") || "Keine Ticker in Watchlist"}
              </div>
              <div className="text-xs text-[var(--text-muted)] mt-1">
                (werden nicht in dieser Liste angezeigt)
              </div>
            </div>

            {/* Existing Custom Terms UI */}
            <div className="grid gap-4 md:grid-cols-[2fr_1fr_auto] mb-4">
              <input
                value={newTerm}
                onChange={(e) => setNewTerm(e.target.value)}
                placeholder="Suchbegriff (z.B. Federal Reserve rates)"
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
              />
              <select
                value={newCategory}
                onChange={(e) => setNewCategory(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
              >
                {["macro", "geopolitik", "sector", "earnings", "commodities", "custom"].map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
              <button
                onClick={handleAddTerm}
                disabled={!newTerm.trim() || termAction === "add"}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-semibold text-white shadow hover:opacity-90 disabled:opacity-50"
              >
                <Plus size={16} /> {termAction === "add" ? "Hinzufügen..." : "Hinzufügen"}
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-[var(--border)]">
                  <tr>
                    <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Begriff</th>
                    <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Kategorie</th>
                    <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Hinzugefügt</th>
                    <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Aktionen</th>
                  </tr>
                </thead>
                <tbody>
                  {termsLoading ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-[var(--text-muted)]">Lade Suchbegriffe...</td>
                    </tr>
                  ) : searchTerms.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-4 py-6 text-center text-[var(--text-muted)]">Noch keine benutzerdefinierten Begriffe.</td>
                    </tr>
                  ) : (
                    searchTerms.map((term) => (
                      <tr key={term.id || term.term} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)]">
                        <td className="px-4 py-3 font-medium text-[var(--text-primary)]">{term.term}</td>
                        <td className="px-4 py-3 text-[var(--text-secondary)] capitalize">{term.category || "custom"}</td>
                        <td className="px-4 py-3 text-[var(--text-secondary)]">
                          {term.created_at ? new Date(term.created_at).toLocaleDateString("de-DE") : "-"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button
                            onClick={() => handleRemoveTerm(term.term)}
                            disabled={termAction === term.term}
                            className="inline-flex items-center gap-1 rounded-lg border border-[var(--border)] px-3 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)] disabled:opacity-50"
                          >
                            <Trash2 size={14} /> {termAction === term.term ? "Entferne..." : "Entfernen"}
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* News Memory Status */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">News-Memory Status</h3>
            <p className="text-sm text-[var(--text-secondary)] mb-4">Was wurde zuletzt gespeichert?</p>
            <div className="flex gap-3 mb-4">
              <select
                value={selectedTicker}
                onChange={(e) => setSelectedTicker(e.target.value)}
                className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
              >
                <option value="">Ticker wählen...</option>
                {watchlist.map(item => (
                  <option key={item.ticker} value={item.ticker}>{item.ticker} – {item.company_name}</option>
                ))}
              </select>
              <button
                onClick={() => selectedTicker && loadNewsMemory(selectedTicker)}
                disabled={!selectedTicker}
                className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-50"
              >
                <Search size={16} />
                Laden
              </button>
            </div>
            {newsMemory && (
              <div className="text-sm text-[var(--text-secondary)]">
                <div>Anzahl gespeicherter Stichpunkte: <span className="font-bold text-[var(--text-primary)]">{newsMemory.count}</span></div>
                {newsMemory.last_date && (
                  <div>Letztes Datum: <span className="font-bold text-[var(--text-primary)]">{newsMemory.last_date}</span></div>
                )}
                {newsMemory.latest_bullet && (
                  <div className="mt-2 p-2 bg-[var(--bg-tertiary)] rounded">
                    <div className="font-medium text-[var(--text-primary)] mb-1">Letzter Stichpunkt:</div>
                    <div className="text-xs">{newsMemory.latest_bullet}</div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === "konfiguration" && (
        <div className="space-y-6">
          {/* Scoring Weights */}
          {scoringConfig && (
            <div className="card p-6">
              <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Scoring-Gewichtungen (Read-Only)</h3>
              <p className="text-sm text-[var(--text-secondary)] mb-4">
                Gewichtungen können in config/scoring.yaml geändert werden. Backend-Neustart erforderlich.
              </p>
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h4 className="font-medium text-[var(--text-primary)] mb-3">Opportunity-Score (9 Faktoren)</h4>
                  <div className="space-y-2">
                    {Object.entries(scoringConfig?.opportunity_score || {}).map(([key, weight]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-[var(--text-secondary)]">{key.replace(/_/g, " ")}</span>
                        <span className="font-mono text-[var(--text-primary)]">{((weight as number) * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <h4 className="font-medium text-[var(--text-primary)] mb-3">Torpedo-Score (7 Faktoren)</h4>
                  <div className="space-y-2">
                    {Object.entries(scoringConfig?.torpedo_score || {}).map(([key, weight]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-[var(--text-secondary)]">{key.replace(/_/g, " ")}</span>
                        <span className="font-mono text-[var(--text-primary)]">{((weight as number) * 100).toFixed(0)}%</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
              {scoringConfig?.thresholds && (
                <div className="mt-6 pt-4 border-t border-[var(--border)]">
                  <h4 className="font-medium text-[var(--text-primary)] mb-3">Thresholds</h4>
                  <div className="grid gap-2 md:grid-cols-2">
                    {Object.entries(scoringConfig.thresholds).map(([key, val]) => (
                      <div key={key} className="flex justify-between text-sm">
                        <span className="text-[var(--text-secondary)]">{key.replace(/_/g, " ")}</span>
                        <span className="font-mono text-[var(--text-primary)]">{String(val)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Platform Info */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">System-Architektur</h3>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Infrastruktur</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>Version: v5.11.2</div>
                  <div>Umgebung: production (Docker Swarm)</div>
                  <div>Hardware: NUC i3 / 16GB RAM / ZimaOS</div>
                  <div>Container: Backend (FastAPI) + Frontend (Next.js) + n8n</div>
                  <div>Datenbank: Supabase (PostgreSQL)</div>
                  <div>Cache: Redis (Session + API Cache)</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">n8n Automation</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>Mo-Fr 08:00 — Morning Briefing (Watchlist)</div>
                  <div>Mo-Fr 13:00-22:30 alle 30 Min — News-Pipeline</div>
                  <div>Mo-Fr 22:00 — Sonntags-Report Vorbereitung</div>
                  <div>So 19:00 — Sonntags-Report (PDF)</div>
                  <div>Sa/So 10/14/18/22 — News-Pipeline (Wochenende)</div>
                  <div>alle 10 Min — SEC EDGAR Scan</div>
                </div>
              </div>
            </div>
          </div>

          {/* Data Flows */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Datenflüsse & APIs</h3>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Marktdaten (Real-time)</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• yfinance — Preise, Technicals, Fundamentals</div>
                  <div>• Finnhub — News, Economic Calendar, Insider</div>
                  <div>• FMP — Financial Modeling Prep (Earnings)</div>
                  <div>• FRED — Makro-Indikatoren (Zinsen, spreads)</div>
                  <div>• FinBERT — Sentiment Analysis (DL-Model)</div>
                  <div>• Google News RSS — General News Feed</div>
                  <div>• SEC EDGAR — Filings, 8-K, 10-Q/K</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Verarbeitung & Storage</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• Daily Snapshots — Preis- + Indikator-Status</div>
                  <div>• Macro Snapshots — FRED-Zeitreihen</div>
                  <div>• Short-term Memory — News + Sentiment</div>
                  <div>• Audit Reports — Generierte Berichte</div>
                  <div>• Watchlist — Benutzer-Ticker</div>
                  <div>• Scoring History — Opportunity/Torpedo Scores</div>
                  <div>• Log Buffer — In-Memory (letzten 500)</div>
                </div>
              </div>
            </div>
          </div>

          {/* Configuration Points */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Konfigurationspunkte</h3>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Backend Config</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• <code>config/scoring.yaml</code> — Score-Gewichtungen</div>
                  <div>• <code>config/.env</code> — API Keys, Supabase</div>
                  <div>• <code>backend/app/logger.py</code> — Module-Definition</div>
                  <div>• <code>docker-compose.yml</code> — Container-Setup</div>
                  <div>• <code>n8n/workflows/</code> — Automation-Definitionen</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Frontend Config</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• <code>frontend/src/app/globals.css</code> — Design Tokens</div>
                  <div>• <code>frontend/src/lib/api.ts</code> — API-Client</div>
                  <div>• <code>frontend/next.config.ts</code> — Proxy + Build</div>
                  <div>• <code>frontend/src/components/</code> — UI-Komponenten</div>
                  <div>• <code>frontend/src/app/</code> — Seiten & API-Routes</div>
                </div>
              </div>
            </div>
          </div>

          {/* Feature Matrix */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Feature-Matrix</h3>
            <div className="space-y-4">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Core Features</h4>
                <div className="grid gap-2 md:grid-cols-3 text-sm">
                  <div className="text-[var(--text-secondary)]">• Marktdashboard (9 Kacheln)</div>
                  <div className="text-[var(--text-secondary)]">• Watchlist + Research</div>
                  <div className="text-[var(--text-secondary)]">• Earnings-Radar</div>
                  <div className="text-[var(--text-secondary)]">• News-Feed + Sentiment</div>
                  <div className="text-[var(--text-secondary)]">• Performance-Analyse</div>
                  <div className="text-[var(--text-secondary)]">• Reports (PDF)</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Advanced Features</h4>
                <div className="grid gap-2 md:grid-cols-3 text-sm">
                  <div className="text-[var(--text-secondary)]">• Composite Regime Scoring</div>
                  <div className="text-[var(--text-secondary)]">• Position Sizer (Risk)</div>
                  <div className="text-[var(--text-secondary)]">• Expected Move Calculator</div>
                  <div className="text-[var(--text-secondary)]">• Market Breadth Analysis</div>
                  <div className="text-[var(--text-secondary)]">• Intermarket Signals</div>
                  <div className="text-[var(--text-secondary)]">• Economic Calendar</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">System Features</h4>
                <div className="grid gap-2 md:grid-cols-3 text-sm">
                  <div className="text-[var(--text-secondary)]">• Command Center (Settings)</div>
                  <div className="text-[var(--text-secondary)]">• Module-Status Monitoring</div>
                  <div className="text-[var(--text-secondary)]">• Log-Viewer (Global)</div>
                  <div className="text-[var(--text-secondary)]">• API-Diagnostics</div>
                  <div className="text-[var(--text-secondary)]">• Telegram-Integration</div>
                  <div className="text-[var(--text-secondary)]">• Automated Reports</div>
                </div>
              </div>
            </div>
          </div>

          {/* Development Notes */}
          <div className="card p-6">
            <h3 className="text-lg font-bold text-[var(--text-primary)] mb-4">Entwicklung & Wartung</h3>
            <div className="grid gap-6 md:grid-cols-2">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Tech Stack</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• Backend: Python 3.11, FastAPI, asyncio</div>
                  <div>• Frontend: React 18, Next.js 16, TypeScript</div>
                  <div>• Database: PostgreSQL (Supabase)</div>
                  <div>• Cache: Redis (Session + API)</div>
                  <div>• ML: Transformers (FinBERT), scikit-learn</div>
                  <div>• Automation: n8n (Node-RED Alternative)</div>
                </div>
              </div>
              <div>
                <h4 className="font-medium text-[var(--text-primary)] mb-2">Wichtige Pfade</h4>
                <div className="text-sm text-[var(--text-secondary)] space-y-1">
                  <div>• <code>/logs</code> — System-Logs (Live)</div>
                  <div>• <code>/status</code> — Legacy Status (deprecated)</div>
                  <div>• <code>/settings</code> — Command Center</div>
                  <div>• <code>/api/diagnostics/*</code> — Health-Checks</div>
                  <div>• <code>/api/logs/*</code> — Log-Management</div>
                  <div>• <code>docker-compose logs -f</code> — Container Logs</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

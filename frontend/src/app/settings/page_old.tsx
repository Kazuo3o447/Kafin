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
  tables?: Array<{ table_name: string; row_count: number }>;
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
  last_run_relative?: string;
  last_log_entry?: string;
};

type ModuleStatusResponse = {
  modules: ModuleStatus[];
  timestamp: string;
};

type LogStats = {
  total_logs: number;
  errors: number;
  warnings: number;
  info: number;
  recent_errors: string[];
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
  opportunity_score: {
    factors: Record<string, { weight: number; description: string }>;
  };
  torpedo_score: {
    factors: Record<string, { weight: number; description: string }>;
  };
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
      setErrorLogs(data.logs || []);
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
      const result = await apiCall();
      const actionResult: ActionResult = {
        action: actionId,
        success: true,
        message: typeof result === "string" ? result : JSON.stringify(result),
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
      const response = await fetch("/api/finbert/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: finbertTestText }),
      });
      const data = await response.json();
      setFinbertResult(data);
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

  useEffect(() => {
    loadSearchTerms();
  }, []);

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

  function getStatusIcon(status?: string) {
    if (status === "ok" || status === "success") return <CheckCircle size={20} className="text-[var(--accent-green)]" />;
    if (status === "warning") return <AlertTriangle size={20} className="text-[var(--accent-amber)]" />;
    return <XCircle size={20} className="text-[var(--accent-red)]" />;
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
          {[
            { id: "uebersicht" as TabId, label: "Übersicht", icon: Activity },
            { id: "pipeline" as TabId, label: "Pipeline", icon: Zap },
            { id: "apis" as TabId, label: "APIs", icon: Globe },
            { id: "daten" as TabId, label: "Daten", icon: Database },
            { id: "konfiguration" as TabId, label: "Konfiguration", icon: Settings },
          ].map((tab) => (
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

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">System Check</h2>
          <button
            onClick={runDiagnostics}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-6 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            {loading ? "Running..." : "Run Diagnostics"}
          </button>
        </div>

        <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-4">
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
            const status = diagnostics[key as keyof DiagnosticResult];
            return (
              <div key={key} className="card p-5">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-bold text-[var(--text-primary)]">{label}</h3>
                  {getStatusIcon(status?.status)}
                </div>
                <p className="text-xs text-[var(--text-muted)] leading-relaxed">{status?.details || "Not tested yet"}</p>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-[var(--text-primary)]">🔍 Google News Suchbegriffe</h2>
            <p className="text-sm text-[var(--text-secondary)]">Benutzerdefinierte Suchbegriffe für den RSS-Scanner (Watchlist-Ticker werden automatisch ergänzt).</p>
          </div>
          <button
            onClick={loadSearchTerms}
            disabled={termsLoading}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] disabled:opacity-50"
          >
            {termsLoading ? "Lädt..." : "Reload"}
          </button>
        </div>

        <div className="card space-y-4 p-6">
          <div className="grid gap-4 md:grid-cols-[2fr_1fr_auto]">
            <input
              value={newTerm}
              onChange={(e) => setNewTerm(e.target.value)}
              placeholder="Suchbegriff (z.B. Federal Reserve rates)"
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
            />
            <select
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)]"
            >
              {["macro", "geopolitik", "sector", "earnings", "commodities", "custom"].map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                </option>
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
      </div>

      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold text-[var(--text-primary)]">Database Status</h2>
          <button
            onClick={loadDbStatus}
            disabled={loading}
            className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-6 py-3 text-sm font-medium text-[var(--text-primary)] shadow-sm hover:bg-[var(--bg-tertiary)] disabled:opacity-50 transition-all"
          >
            <Database size={18} />
            {loading ? "Loading..." : "Load DB Status"}
          </button>
        </div>

        <div className="card p-6">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b border-[var(--border)]">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold text-[var(--text-secondary)]">Table</th>
                  <th className="px-4 py-3 text-right font-semibold text-[var(--text-secondary)]">Row Count</th>
                </tr>
              </thead>
              <tbody>
                {dbStatus.tables && dbStatus.tables.length > 0 ? (
                  dbStatus.tables.map((table, idx) => (
                    <tr key={idx} className="border-b border-[var(--border)] hover:bg-[var(--bg-tertiary)] transition-colors">
                      <td className="px-4 py-4 font-medium text-[var(--text-primary)]">{table.table_name}</td>
                      <td className="px-4 py-4 text-right text-[var(--text-primary)]">{table.row_count}</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={2} className="px-4 py-12 text-center text-[var(--text-muted)]">
                      No data available. Click "Load DB Status".
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="card p-6">
          <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">Telegram Test</h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4 leading-relaxed">
            Sends a test message to your Telegram bot.
          </p>
          <button
            onClick={testTelegram}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            Send Test Message
          </button>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-bold text-[var(--text-primary)] mb-2">n8n Workflows</h2>
          <p className="text-sm text-[var(--text-secondary)] mb-4 leading-relaxed">
            Automatically sets up all n8n workflows.
          </p>
          <button
            onClick={setupN8n}
            disabled={loading}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-purple)] px-4 py-3 text-sm font-medium text-white shadow-md hover:opacity-90 disabled:opacity-50 transition-all"
          >
            <Play size={18} />
            Setup Workflows
          </button>
        </div>
      </div>
    </div>
  );
}

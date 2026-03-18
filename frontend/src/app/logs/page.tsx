"use client";

import { useState, useEffect } from "react";
import { Info, AlertTriangle, XCircle, Circle, Filter, Download, Search, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";

type LogEntry = {
  timestamp?: string;
  level?: string;
  logger?: string;
  event?: string;
  source?: string;
  ticker?: string;
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [activeFilter, setActiveFilter] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  async function loadLogs() {
    setLoading(true);
    try {
      const data = await api.getLogs();
      setLogs(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Logs fetch error", error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLogs();
  }, []);

  // Auto-Refresh alle 5 Sekunden
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      loadLogs();
    }, 5000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const exportLogs = () => {
    const dataStr = JSON.stringify(filteredLogs, null, 2);
    const dataBlob = new Blob([dataStr], { type: "application/json" });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `kafin-logs-${new Date().toISOString()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const filteredLogs = logs.filter((log) => {
    // Level Filter
    if (activeFilter !== "all" && log.level !== activeFilter) return false;
    
    // Severity Filter
    if (severityFilter !== "all" && log.level !== severityFilter) return false;
    
    // Search Query
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const eventMatch = log.event?.toLowerCase().includes(query);
      const loggerMatch = log.logger?.toLowerCase().includes(query);
      const tickerMatch = log.ticker?.toLowerCase().includes(query);
      if (!eventMatch && !loggerMatch && !tickerMatch) return false;
    }
    
    return true;
  });

  const getLevelBadgeClass = (level?: string) => {
    switch (level) {
      case "error":
        return "badge-danger";
      case "warning":
        return "badge-warning";
      case "info":
        return "badge-info";
      case "debug":
        return "badge-neutral";
      default:
        return "badge-neutral";
    }
  };

  const logCounts = {
    all: logs.length,
    info: logs.filter((l) => l.level === "info").length,
    warning: logs.filter((l) => l.level === "warning").length,
    error: logs.filter((l) => l.level === "error").length,
  };

  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-3xl font-bold text-[var(--text-primary)]">System Logs</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">Echtzeit-Monitoring der Backend-Aktivitäten</p>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Search size={18} className="text-[var(--text-muted)]" />
            <input
              type="text"
              placeholder="Suche in Logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent-blue)] w-80"
            />
          </div>
          <div className="flex items-center gap-3">
            {lastUpdate && (
              <span className="text-xs text-[var(--text-muted)]">
                Zuletzt: {lastUpdate.toLocaleTimeString("de-DE")}
              </span>
            )}
            <button
              onClick={exportLogs}
              className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] shadow-sm hover:bg-[var(--bg-tertiary)] transition-all"
            >
              <Download size={16} />
              Export
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setActiveFilter("all")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeFilter === "all"
                  ? "bg-[var(--accent-blue)] text-white shadow-md"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border)]"
              }`}
            >
              Alle <span className="ml-1 opacity-75">({logCounts.all})</span>
            </button>
            <button
              onClick={() => setActiveFilter("info")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeFilter === "info"
                  ? "bg-[var(--accent-blue)] text-white shadow-md"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border)]"
              }`}
            >
              Info <span className="ml-1 opacity-75">({logCounts.info})</span>
            </button>
            <button
              onClick={() => setActiveFilter("warning")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeFilter === "warning"
                  ? "bg-[var(--accent-amber)] text-white shadow-md"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border)]"
              }`}
            >
              Warnings <span className="ml-1 opacity-75">({logCounts.warning})</span>
            </button>
            <button
              onClick={() => setActiveFilter("error")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                activeFilter === "error"
                  ? "bg-[var(--accent-red)] text-white shadow-md"
                  : "bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--border)]"
              }`}
            >
              Errors <span className="ml-1 opacity-75">({logCounts.error})</span>
            </button>
          </div>

          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
              <input
                type="checkbox"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.target.checked)}
                className="h-4 w-4 rounded border-[var(--border)] accent-[var(--accent-blue)]"
              />
              Auto-Refresh (5s)
            </label>
            <button
              onClick={loadLogs}
              disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-4 py-2 text-sm font-medium text-white shadow-sm hover:opacity-90 disabled:opacity-50 transition-all"
            >
              <RefreshCw size={16} className={loading ? "animate-spin" : ""} />
              Aktualisieren
            </button>
          </div>
        </div>

        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          {loading && filteredLogs.length === 0 ? (
            <div className="text-center py-12">
              <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-[var(--accent-blue)] border-r-transparent"></div>
              <p className="text-sm text-[var(--text-muted)] mt-4">Lade Logs...</p>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-[var(--text-muted)]">Keine Logs verfügbar</p>
            </div>
          ) : (
            filteredLogs.map((log, idx) => (
              <div
                key={idx}
                className="flex items-start gap-4 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-4 transition-all hover:shadow-sm"
              >
                <div className="flex-shrink-0 mt-0.5">
                  <Circle
                    size={8}
                    className={
                      log.level === "error"
                        ? "fill-[var(--accent-red)] text-[var(--accent-red)]"
                        : log.level === "warning"
                        ? "fill-[var(--accent-amber)] text-[var(--accent-amber)]"
                        : log.level === "info"
                        ? "fill-[var(--accent-blue)] text-[var(--accent-blue)]"
                        : "fill-[var(--text-muted)] text-[var(--text-muted)]"
                    }
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-1">
                    <span className={`badge ${getLevelBadgeClass(log.level)}`}>{log.level?.toUpperCase()}</span>
                    <span className="text-xs text-[var(--text-muted)]">{log.timestamp}</span>
                  </div>
                  <p className="text-sm text-[var(--text-primary)] mb-1">{log.event}</p>
                  {log.logger && (
                    <p className="text-xs text-[var(--text-muted)] font-mono">{log.logger}</p>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

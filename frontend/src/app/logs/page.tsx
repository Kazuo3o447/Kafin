"use client";

import { useState, useEffect } from "react";
import { FileText, Play, CheckCircle, XCircle, AlertTriangle } from "lucide-react";

type LogEntry = {
  timestamp?: string;
  level?: string;
  logger?: string;
  event?: string;
};

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [logLevel, setLogLevel] = useState<string>("all");
  const [showDebug, setShowDebug] = useState(false);

  useEffect(() => {
    loadLogs();
    if (autoRefresh) {
      const interval = setInterval(() => {
        loadLogs();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  async function loadLogs() {
    setLoading(true);
    try {
      const result = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/logs`).then((r) =>
        r.json()
      );
      setLogs(result.logs || []);
    } catch (error) {
      console.error("Logs fetch error", error);
    } finally {
      setLoading(false);
    }
  }

  const filteredLogs = logs.filter((log) => {
    if (!showDebug && log.level === "debug") return false;
    if (logLevel !== "all" && log.level !== logLevel) return false;
    return true;
  });

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-[var(--text-muted)]">Logs</p>
        <h1 className="text-3xl font-semibold text-[var(--text-primary)]">Live-Logs</h1>
        <p className="text-sm text-[var(--text-secondary)]">Echtzeit-Logs aus dem Kafin Backend</p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input
            type="checkbox"
            checked={showDebug}
            onChange={(e) => setShowDebug(e.target.checked)}
            className="rounded border-[var(--border)]"
          />
          Debug anzeigen
        </label>
        <select
          value={logLevel}
          onChange={(e) => setLogLevel(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-1 text-sm text-[var(--text-primary)] outline-none"
        >
          <option value="all">Alle Levels</option>
          <option value="info">INFO</option>
          <option value="warning">WARNING</option>
          <option value="error">ERROR</option>
        </select>
        <label className="flex items-center gap-2 text-sm text-[var(--text-secondary)]">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="rounded border-[var(--border)]"
          />
          Auto-Refresh (5s)
        </label>
        <button
          onClick={loadLogs}
          className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-1 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]"
        >
          <Play size={16} />
          Aktualisieren
        </button>
      </div>

      <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-secondary)] p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-[0.3em] text-[var(--text-muted)]">
            Log-Stream
          </h2>
          <div className="flex items-center gap-4 text-xs text-[var(--text-muted)]">
            <span className="flex items-center gap-1">
              <CheckCircle size={14} className="text-[var(--accent-green)]" />
              INFO
            </span>
            <span className="flex items-center gap-1">
              <AlertTriangle size={14} className="text-[var(--accent-amber)]" />
              WARNING
            </span>
            <span className="flex items-center gap-1">
              <XCircle size={14} className="text-[var(--accent-red)]" />
              ERROR
            </span>
          </div>
        </div>
        <div className="mt-4 max-h-[700px] overflow-y-auto rounded-lg bg-[var(--bg-primary)] p-4 font-mono text-xs">
          {loading && filteredLogs.length === 0 ? (
            <p className="text-[var(--text-muted)]">Lade Logs...</p>
          ) : filteredLogs.length === 0 ? (
            <p className="text-[var(--text-muted)]">Keine Logs verfügbar.</p>
          ) : (
            filteredLogs.map((log, idx) => (
              <div
                key={idx}
                className={`border-b border-[var(--border)] py-2 hover:bg-[var(--bg-tertiary)] ${
                  log.level === "error"
                    ? "text-[var(--accent-red)]"
                    : log.level === "warning"
                    ? "text-[var(--accent-amber)]"
                    : log.level === "info"
                    ? "text-[var(--accent-blue)]"
                    : "text-[var(--text-muted)]"
                }`}
              >
                <span className="text-[var(--text-muted)]">[{log.timestamp}]</span>{" "}
                <span className="font-semibold">[{log.level?.toUpperCase()}]</span>{" "}
                <span className="text-[var(--text-secondary)]">{log.logger}</span> - {log.event}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect } from "react";
import { Info, AlertTriangle, XCircle, Circle, RefreshCw, ChevronDown, ChevronRight, Settings, FileText, Activity, Calendar, Shield, Zap } from "lucide-react";
import { api } from "@/lib/api";

// Auto-Refresh intervals in milliseconds
const ERROR_REFRESH_INTERVAL = 60000; // 60 seconds
const MODULE_REFRESH_INTERVAL = 120000; // 120 seconds

type LogEntry = {
  timestamp?: string;
  level?: string;
  logger?: string;
  event?: string;
  source?: string;
  ticker?: string;
};

type ErrorLogEntry = {
  timestamp: string;
  level: string;
  logger: string;
  event: string;
  ticker?: string;
};

type ModuleStatus = {
  label: string;
  status: "ok" | "warning" | "error" | "unknown";
  last_run?: string;
  last_run_relative?: string;
  last_error?: {
    timestamp: string;
    level: string;
    event: string;
  };
  stats: string;
  recent_logs: LogEntry[];
};

type ModuleStatusResponse = {
  modules: Record<string, ModuleStatus>;
  generated_at: string;
};

type ErrorsResponse = {
  errors: ErrorLogEntry[];
  count: number;
};

const MODULE_ICONS: Record<string, React.ReactNode> = {
  finbert_pipeline: <Settings size={20} />,
  sec_edgar: <FileText size={20} />,
  morning_briefing: <Calendar size={20} />,
  sunday_report: <FileText size={20} />,
  torpedo_monitor: <Shield size={20} />,
  n8n_scheduler: <Zap size={20} />,
};

export default function LogsPage() {
  const [errors, setErrors] = useState<ErrorLogEntry[]>([]);
  const [moduleStatus, setModuleStatus] = useState<ModuleStatusResponse | null>(null);
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [expandedErrors, setExpandedErrors] = useState<Set<number>>(new Set());
  const [showRawLogs, setShowRawLogs] = useState(false);
  const [rawLogs, setRawLogs] = useState<LogEntry[]>([]);
  const [errorsLastUpdate, setErrorsLastUpdate] = useState<Date | null>(null);
  const [modulesLastUpdate, setModulesLastUpdate] = useState<Date | null>(null);

  // Load errors
  async function loadErrors() {
    try {
      const data: ErrorsResponse = await api.get("/api/logs/errors");
      setErrors(data.errors);
      setErrorsLastUpdate(new Date());
    } catch (error) {
      console.error("Errors fetch error", error);
    }
  }

  // Load module status
  async function loadModuleStatus() {
    try {
      const data: ModuleStatusResponse = await api.get("/api/logs/module-status");
      setModuleStatus(data);
      setModulesLastUpdate(new Date());
    } catch (error) {
      console.error("Module status fetch error", error);
    }
  }

  // Load raw logs (on-demand)
  async function loadRawLogs() {
    try {
      const data: LogEntry[] = await api.get("/api/logs");
      setRawLogs(data);
    } catch (error) {
      console.error("Raw logs fetch error", error);
    }
  }

  // Load module logs (on-demand)
  async function loadModuleLogs(moduleId: string) {
    try {
      const data: { logs: LogEntry[] } = await api.get(`/api/logs/module/${moduleId}`);
      if (moduleStatus) {
        setModuleStatus({
          ...moduleStatus,
          modules: {
            ...moduleStatus.modules,
            [moduleId]: {
              ...moduleStatus.modules[moduleId],
              recent_logs: data.logs,
            },
          },
        });
      }
    } catch (error) {
      console.error(`Module logs fetch error for ${moduleId}`, error);
    }
  }

  // Initial load
  useEffect(() => {
    loadErrors();
    loadModuleStatus();
  }, []);

  // Auto-refresh errors
  useEffect(() => {
    const interval = setInterval(loadErrors, ERROR_REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  // Auto-refresh module status
  useEffect(() => {
    const interval = setInterval(loadModuleStatus, MODULE_REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const toggleModule = (moduleId: string) => {
    const newExpanded = new Set(expandedModules);
    if (newExpanded.has(moduleId)) {
      newExpanded.delete(moduleId);
    } else {
      newExpanded.add(moduleId);
      // Load logs on first expand
      if (!moduleStatus?.modules[moduleId].recent_logs.length) {
        loadModuleLogs(moduleId);
      }
    }
    setExpandedModules(newExpanded);
  };

  const toggleError = (index: number) => {
    const newExpanded = new Set(expandedErrors);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedErrors(newExpanded);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "ok":
        return "text-green-500";
      case "warning":
        return "text-yellow-500";
      case "error":
        return "text-red-500";
      default:
        return "text-gray-500";
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "ok":
        return <Circle size={12} className="fill-green-500 text-green-500" />;
      case "warning":
        return <AlertTriangle size={12} className="text-yellow-500" />;
      case "error":
        return <XCircle size={12} className="text-red-500" />;
      default:
        return <Circle size={12} className="text-gray-500" />;
    }
  };

  const getLevelColor = (level: string) => {
    switch (level.toLowerCase()) {
      case "error":
        return "text-red-500";
      case "warning":
        return "text-yellow-500";
      case "info":
        return "text-blue-500";
      case "debug":
        return "text-gray-500";
      default:
        return "text-gray-500";
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-[var(--text-primary)]">System Heartbeat</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">System-Health-Überblick der Kernmodule</p>
      </div>

      {/* Error/Warning Inbox */}
      <div className={`card p-6 border-2 ${
        errors.some(e => e.level === "error") ? "border-red-500" :
        errors.some(e => e.level === "warning") ? "border-yellow-500" :
        "border-green-500"
      }`}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <AlertTriangle size={20} />
            Fehler & Warnungen
          </h2>
          <div className="flex items-center gap-3">
            {errorsLastUpdate && (
              <span className="text-xs text-[var(--text-muted)]">
                Zuletzt aktualisiert: {errorsLastUpdate.toLocaleTimeString("de-DE")}
              </span>
            )}
            <button
              onClick={loadErrors}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>

        {errors.length === 0 ? (
          <div className="text-center py-6 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
            <Circle size={24} className="text-green-500 mx-auto mb-2" />
            <p className="text-sm text-green-700 dark:text-green-300">Alle Systeme normal</p>
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {errors.map((error, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-3"
              >
                <div className="flex-shrink-0 mt-0.5">
                  {error.level === "error" ? (
                    <XCircle size={16} className="text-red-500" />
                  ) : (
                    <AlertTriangle size={16} className="text-yellow-500" />
                  )}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs font-semibold ${getLevelColor(error.level)}`}>
                      {error.level.toUpperCase()}
                    </span>
                    <span className="text-xs text-[var(--text-muted)]">{error.timestamp}</span>
                    <span className="text-xs text-[var(--text-muted)] font-mono">{error.logger}</span>
                  </div>
                  <p className="text-sm text-[var(--text-primary)]">
                    {expandedErrors.has(idx) || error.event.length <= 120
                      ? error.event
                      : `${error.event.substring(0, 120)}...`}
                  </p>
                  {error.event.length > 120 && (
                    <button
                      onClick={() => toggleError(idx)}
                      className="text-xs text-[var(--accent-blue)] hover:underline mt-1"
                    >
                      {expandedErrors.has(idx) ? "Weniger anzeigen" : "Mehr anzeigen"}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Module Status Grid */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-[var(--text-primary)] flex items-center gap-2">
            <Activity size={20} />
            Modul-Status
          </h2>
          <div className="flex items-center gap-3">
            {modulesLastUpdate && (
              <span className="text-xs text-[var(--text-muted)]">
                Zuletzt aktualisiert: {modulesLastUpdate.toLocaleTimeString("de-DE")}
              </span>
            )}
            <button
              onClick={loadModuleStatus}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] px-3 py-1.5 text-sm font-medium text-white shadow-sm hover:opacity-90 transition-all"
            >
              <RefreshCw size={14} />
              Refresh
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {moduleStatus && Object.entries(moduleStatus.modules).map(([moduleId, module]) => (
            <div
              key={moduleId}
              className="border border-[var(--border)] bg-[var(--bg-secondary)] rounded-lg p-4"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="text-[var(--text-muted)]">
                  {MODULE_ICONS[moduleId]}
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-[var(--text-primary)]">{module.label}</h3>
                </div>
                <div className={getStatusColor(module.status)}>
                  {getStatusIcon(module.status)}
                </div>
              </div>

              <div className="space-y-2 mb-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-[var(--text-secondary)]">Status:</span>
                  <span className={`text-sm font-semibold ${getStatusColor(module.status)}`}>
                    {module.status.toUpperCase()}
                    {module.last_run_relative && ` — ${module.last_run_relative}`}
                  </span>
                </div>
                {module.last_run && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[var(--text-secondary)]">Letzter Run:</span>
                    <span className="text-xs text-[var(--text-muted)] font-mono">
                      {new Date(module.last_run).toLocaleString("de-DE")}
                    </span>
                  </div>
                )}
                {module.stats && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-[var(--text-secondary)]">Stats:</span>
                    <span className="text-xs text-[var(--text-muted)]">{module.stats}</span>
                  </div>
                )}
              </div>

              <button
                onClick={() => toggleModule(moduleId)}
                className="w-full flex items-center justify-center gap-2 rounded border border-[var(--border)] bg-[var(--bg-tertiary)] px-3 py-1.5 text-sm text-[var(--text-primary)] hover:bg-[var(--bg-primary)] transition-all"
              >
                {expandedModules.has(moduleId) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                {expandedModules.has(moduleId) ? "Details verbergen" : "Details anzeigen"}
              </button>

              {expandedModules.has(moduleId) && (
                <div className="mt-3 pt-3 border-t border-[var(--border)]">
                  <div className="space-y-1 max-h-32 overflow-y-auto">
                    {module.recent_logs.length > 0 ? (
                      module.recent_logs.map((log, idx) => (
                        <div key={idx} className="text-xs font-mono">
                          <span className={getLevelColor(log.level || "")}>
                            {log.level?.toUpperCase()}
                          </span>
                          <span className="text-[var(--text-muted)] ml-2">
                            {log.timestamp?.substring(11, 19)}
                          </span>
                          <span className="text-[var(--text-primary)] ml-2">
                            {log.event?.substring(0, 80)}
                            {log.event && log.event.length > 80 ? "..." : ""}
                          </span>
                        </div>
                      ))
                    ) : (
                      <p className="text-xs text-[var(--text-muted)]">Keine Logs verfügbar</p>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Raw Log Viewer (Advanced) */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">Erweitert</h2>
        </div>
        
        <button
          onClick={() => {
            setShowRawLogs(!showRawLogs);
            if (!showRawLogs && rawLogs.length === 0) {
              loadRawLogs();
            }
          }}
          className="flex items-center gap-2 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] px-4 py-2 text-sm font-medium text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] transition-all"
        >
          {showRawLogs ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          {showRawLogs ? "Raw Logs verbergen" : "Raw Logs anzeigen"}
        </button>

        {showRawLogs && (
          <div className="mt-4 space-y-2 max-h-96 overflow-y-auto">
            {rawLogs.map((log, idx) => (
              <div
                key={idx}
                className="flex items-start gap-3 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-3"
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
                    <span className={`text-xs font-semibold ${getLevelColor(log.level || "")}`}>
                      {log.level?.toUpperCase()}
                    </span>
                    <span className="text-xs text-[var(--text-muted)]">{log.timestamp}</span>
                    {log.logger && (
                      <span className="text-xs text-[var(--text-muted)] font-mono">{log.logger}</span>
                    )}
                  </div>
                  <p className="text-sm text-[var(--text-primary)] font-mono">{log.event}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

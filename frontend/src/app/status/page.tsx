"use client";

import { useState, useEffect } from "react";
import { Activity, AlertCircle, CheckCircle, Clock } from "lucide-react";

type ServiceStatus = {
  status: "ok" | "warning" | "error";
  latency_ms?: number;
  details?: string;
  error_code?: string;
};

type DiagnosticsResponse = {
  status: "ok" | "degraded";
  timestamp: string;
  services: Record<string, ServiceStatus>;
};

export default function StatusPage() {
  const [diagnostics, setDiagnostics] = useState<DiagnosticsResponse | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const loadDiagnostics = async () => {
    try {
      const response = await fetch("/api/diagnostics/full");
      const data = await response.json();
      setDiagnostics(data);
      setLastUpdate(new Date());
    } catch (error) {
      console.error("Failed to fetch diagnostics:", error);
    }
  };

  useEffect(() => {
    loadDiagnostics();
    const interval = setInterval(loadDiagnostics, 30000);
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    if (status === "ok") return <CheckCircle className="text-green-500" size={20} />;
    if (status === "warning") return <AlertCircle className="text-yellow-500" size={20} />;
    return <AlertCircle className="text-red-500 animate-pulse" size={20} />;
  };

  const getStatusColor = (status: string) => {
    if (status === "ok") return "border-green-500 bg-green-50 dark:bg-green-900/20";
    if (status === "warning") return "border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20";
    return "border-red-500 bg-red-50 dark:bg-red-900/20";
  };

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold text-[var(--text-primary)]">System Status</h1>
        <p className="text-sm text-[var(--text-secondary)] mt-2">
          Real-time monitoring of all critical services
          {lastUpdate && (
            <span className="ml-2 text-[var(--text-muted)]">
              • Last update: {lastUpdate.toLocaleTimeString("de-DE")}
            </span>
          )}
        </p>
      </div>

      {/* System Core Health */}
      <div className="card p-6">
        <div className="flex items-center gap-2 mb-6">
          <Activity size={24} className="text-[var(--accent-blue)]" />
          <h2 className="text-xl font-semibold text-[var(--text-primary)]">System Core Health</h2>
        </div>

        {!diagnostics ? (
          <div className="text-center py-8 text-[var(--text-muted)]">Loading diagnostics...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(diagnostics.services).map(([name, service]) => (
              <div
                key={name}
                className={`border-2 rounded-lg p-4 ${getStatusColor(service.status)}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(service.status)}
                    <h3 className="font-semibold text-[var(--text-primary)] uppercase text-sm">
                      {name}
                    </h3>
                  </div>
                  {service.latency_ms !== undefined && (
                    <div className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
                      <Clock size={12} />
                      <span>{service.latency_ms}ms</span>
                    </div>
                  )}
                </div>

                {service.status === "error" && (
                  <div className="space-y-1">
                    {service.error_code && (
                      <div className="text-red-500 font-bold text-sm">
                        ERROR: {service.error_code}
                      </div>
                    )}
                    {service.details && (
                      <div className="text-red-500 text-xs font-mono break-all">
                        {service.details}
                      </div>
                    )}
                  </div>
                )}

                {service.status === "ok" && service.details && (
                  <div className="text-xs text-[var(--text-muted)]">{service.details}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Overall System Status */}
      <div className={`card p-6 border-2 ${
        diagnostics?.status === "ok" 
          ? "border-green-500" 
          : "border-red-500"
      }`}>
        <div className="flex items-center gap-3">
          {diagnostics?.status === "ok" ? (
            <CheckCircle className="text-green-500" size={32} />
          ) : (
            <AlertCircle className="text-red-500 animate-pulse" size={32} />
          )}
          <div>
            <h3 className="text-lg font-semibold text-[var(--text-primary)]">
              {diagnostics?.status === "ok" ? "All Systems Operational" : "System Degraded"}
            </h3>
            <p className="text-sm text-[var(--text-secondary)]">
              {diagnostics?.status === "ok"
                ? "All services are running normally"
                : "One or more services are experiencing issues"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useRef } from "react";
import { Play, Pause, Trash2, Download } from "lucide-react";

export default function LogsPage() {
  const [logs, setLogs] = useState<string[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when logs update
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  // Poll logs every 2 seconds when enabled
  useEffect(() => {
    if (!isPolling) return;

    const interval = setInterval(async () => {
      try {
        const response = await fetch("/api/logs/file?lines=1000");
        const data = await response.json();
        setLogs(data.logs || []);
      } catch (error) {
        console.error("Failed to fetch logs:", error);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [isPolling]);

  // Initial load
  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    try {
      const response = await fetch("/api/logs/file?lines=1000");
      const data = await response.json();
      setLogs(data.logs || []);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    }
  };

  const clearLogs = async () => {
    try {
      await fetch("/api/logs/file", { method: "DELETE" });
      setLogs([]);
    } catch (error) {
      console.error("Failed to clear logs:", error);
    }
  };

  const exportLogs = () => {
    window.open("/api/logs/export", "_blank");
  };

  const getLogColor = (line: string) => {
    if (line.includes("[ERROR]") || line.includes("error_code")) {
      return "text-red-500 font-bold";
    }
    if (line.includes("[WARNING]")) {
      return "text-yellow-400";
    }
    return "text-green-400";
  };

  return (
    <div className="bg-black text-green-400 font-mono h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-700 p-4">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-green-400">KAFIN TERMINAL</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsPolling(!isPolling)}
              className="flex items-center gap-2 px-3 py-1 bg-gray-800 text-green-400 rounded hover:bg-gray-700 transition-colors"
            >
              {isPolling ? <Pause size={16} /> : <Play size={16} />}
              {isPolling ? "PAUSE" : "PLAY"}
            </button>
            <button
              onClick={clearLogs}
              className="flex items-center gap-2 px-3 py-1 bg-gray-800 text-red-400 rounded hover:bg-gray-700 transition-colors"
            >
              <Trash2 size={16} />
              CLEAR
            </button>
            <button
              onClick={exportLogs}
              className="flex items-center gap-2 px-3 py-1 bg-gray-800 text-blue-400 rounded hover:bg-gray-700 transition-colors"
            >
              <Download size={16} />
              EXPORT
            </button>
            <button
              onClick={() => setAutoScroll(!autoScroll)}
              className={`px-3 py-1 rounded transition-colors ${
                autoScroll 
                  ? "bg-gray-800 text-green-400" 
                  : "bg-gray-800 text-gray-400"
              }`}
            >
              AUTO-SCROLL: {autoScroll ? "ON" : "OFF"}
            </button>
          </div>
        </div>
      </div>

      {/* Log Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="min-h-full">
          {logs.length === 0 ? (
            <div className="text-gray-500 text-center py-8">
              No logs available. Start polling to see real-time logs.
            </div>
          ) : (
            logs.map((line, index) => (
              <div key={index} className={`whitespace-pre-wrap break-all ${getLogColor(line)}`}>
                {line}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </div>
    </div>
  );
}

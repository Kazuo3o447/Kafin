"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { Terminal, Download, Pause, Play, Trash2, Search, AlertTriangle, AlertCircle, Info, Filter } from "lucide-react";

type LogStats = { total: number; error: number; warning: number; info: number };
type LevelFilter = "all" | "error" | "warning" | "info";

export default function TerminalPage() {
    const [logs, setLogs] = useState<string[]>([]);
    const [stats, setStats] = useState<LogStats>({ total: 0, error: 0, warning: 0, info: 0 });
    const [isPolling, setIsPolling] = useState(true);
    const [autoScroll, setAutoScroll] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
    const bottomRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const fetchLogs = useCallback(async () => {
        if (!isPolling) return;
        try {
            const levelParam = levelFilter !== "all" ? `&level=${levelFilter}` : "";
            const res = await fetch(`/api/logs/file?lines=1000${levelParam}`).then(r => r.json());
            if (res.logs) setLogs(res.logs);
            if (res.stats) setStats(res.stats);
        } catch (e) { console.error(e); }
    }, [isPolling, levelFilter]);

    useEffect(() => {
        fetchLogs();
        const interval = setInterval(fetchLogs, 2000);
        return () => clearInterval(interval);
    }, [fetchLogs]);

    useEffect(() => {
        if (autoScroll && bottomRef.current) bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }, [logs, autoScroll]);

    const handleScroll = () => {
        if (!containerRef.current) return;
        const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
        const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
        if (isAtBottom && !autoScroll) setAutoScroll(true);
        else if (!isAtBottom && autoScroll) setAutoScroll(false);
    };

    const handleExport = () => {
        if (!logs.length) return;
        const blob = new Blob([logs.join('')], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `kafin_terminal_${new Date().toISOString().replace(/[:.]/g, '-')}.log`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const handleClear = async () => {
        if (!confirm("Alle Logs löschen?")) return;
        await fetch("/api/logs/file", { method: "DELETE" });
        setLogs([]);
        setStats({ total: 0, error: 0, warning: 0, info: 0 });
    };

    const filteredLogs = logs.filter(l => l.toLowerCase().includes(searchTerm.toLowerCase()));

    const filterBtn = (level: LevelFilter, label: string, count: number, color: string, bgActive: string) => (
        <button
            onClick={() => setLevelFilter(levelFilter === level ? "all" : level)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded font-mono text-xs transition-all ${
                levelFilter === level
                    ? `${bgActive} ${color} ring-1 ring-current`
                    : `bg-gray-800 text-gray-400 hover:${color}`
            }`}
        >
            {level === "error" && <AlertCircle size={12} />}
            {level === "warning" && <AlertTriangle size={12} />}
            {level === "info" && <Info size={12} />}
            {label}
            <span className={`ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${
                count > 0 && level === "error" ? "bg-red-500/20 text-red-400" :
                count > 0 && level === "warning" ? "bg-yellow-500/20 text-yellow-400" :
                "bg-gray-700 text-gray-400"
            }`}>{count}</span>
        </button>
    );

    return (
        <div className="fixed inset-0 z-50 bg-[#0a0a0a] flex flex-col h-screen overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 bg-[#111] border-b border-gray-800">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <span className="flex h-3 w-3 relative">
                            {isPolling && <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>}
                            <span className={`relative inline-flex rounded-full h-3 w-3 ${isPolling ? 'bg-green-500' : 'bg-gray-600'}`}></span>
                        </span>
                        <Terminal size={18} className="text-green-500" />
                        <span className="text-green-500 font-bold font-mono">KAFIN CORE TERMINAL</span>
                    </div>
                    <div className="relative ml-4">
                        <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input type="text" placeholder="Grep logs..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="bg-[#1a1a1a] border border-gray-700 rounded px-8 py-1 text-sm text-green-400 font-mono focus:outline-none focus:border-green-500 w-64" />
                    </div>
                </div>
                <div className="flex items-center gap-2 font-mono text-xs text-gray-300">
                    <button onClick={() => setIsPolling(!isPolling)} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700">{isPolling ? <Pause size={14}/> : <Play size={14}/>} {isPolling ? 'Pause' : 'Play'}</button>
                    <div className="px-3 py-1.5 rounded border border-gray-700">Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}</div>
                    <button onClick={handleClear} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:text-red-400"><Trash2 size={14}/> Clear</button>
                    <button onClick={handleExport} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:text-white"><Download size={14}/> Export</button>
                </div>
            </div>

            {/* Filter Bar with Stats */}
            <div className="flex items-center justify-between px-4 py-2 bg-[#0d0d0d] border-b border-gray-800/50">
                <div className="flex items-center gap-2">
                    <Filter size={14} className="text-gray-500" />
                    <span className="text-[11px] font-mono text-gray-500 mr-2">LEVEL:</span>
                    <button
                        onClick={() => setLevelFilter("all")}
                        className={`px-2.5 py-1.5 rounded font-mono text-xs transition-all ${
                            levelFilter === "all"
                                ? "bg-gray-700 text-white ring-1 ring-gray-500"
                                : "bg-gray-800 text-gray-400 hover:text-white"
                        }`}
                    >Alle</button>
                    {filterBtn("error", "Errors", stats.error, "text-red-400", "bg-red-950/40")}
                    {filterBtn("warning", "Warnings", stats.warning, "text-yellow-400", "bg-yellow-950/40")}
                    {filterBtn("info", "Info", stats.info, "text-blue-400", "bg-blue-950/40")}
                </div>
                <div className="flex items-center gap-4 font-mono text-[11px] text-gray-500">
                    <span>Zeilen: <span className="text-gray-300">{filteredLogs.length}</span> / {stats.total}</span>
                    {stats.error > 0 && <span className="text-red-400">{stats.error} Errors</span>}
                    {stats.warning > 0 && <span className="text-yellow-400">{stats.warning} Warnings</span>}
                </div>
            </div>

            {/* Log Output */}
            <div ref={containerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-px text-[13px]">
                {filteredLogs.map((log, i) => {
                    const l = log.toLowerCase();
                    const isErr = l.includes("[error]") || l.includes("error_code");
                    const isWarn = l.includes("[warning]");
                    const col = isErr ? "text-red-500 font-bold bg-red-950/20" : isWarn ? "text-yellow-400 bg-yellow-950/10" : "text-green-400";
                    return (
                        <div key={i} className={`flex gap-3 px-2 py-0.5 font-mono break-all whitespace-pre-wrap hover:bg-white/5 ${col}`}>
                            {isErr && <AlertCircle size={14} className="mt-0.5 shrink-0 text-red-500" />}
                            {isWarn && <AlertTriangle size={14} className="mt-0.5 shrink-0 text-yellow-400" />}
                            {log}
                        </div>
                    );
                })}
                <div ref={bottomRef} className="h-4" />
            </div>
        </div>
    );
}

"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { Terminal, Download, Pause, Play, Trash2, Search, AlertTriangle, AlertCircle, Info, Filter, X } from "lucide-react";

type LogStats = { total: number; error: number; warning: number; info: number; ignore: number };
type LevelFilter = "all" | "error" | "warning" | "info" | "ignore";

export function LogViewer() {
    const [isOpen, setIsOpen] = useState(false);
    const [logs, setLogs] = useState<string[]>([]);
    const [stats, setStats] = useState<LogStats>({ total: 0, error: 0, warning: 0, info: 0, ignore: 0 });
    const [isPolling, setIsPolling] = useState(true);
    const [autoScroll, setAutoScroll] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const [levelFilter, setLevelFilter] = useState<LevelFilter>("all");
    const bottomRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleOpen = () => setIsOpen(true);
        const handleToggle = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') {
                e.preventDefault();
                setIsOpen(prev => !prev);
            }
        };
        window.addEventListener("open-log-viewer", handleOpen);
        window.addEventListener("keydown", handleToggle);
        return () => {
            window.removeEventListener("open-log-viewer", handleOpen);
            window.removeEventListener("keydown", handleToggle);
        };
    }, []);

    const fetchLogs = useCallback(async () => {
        if (!isPolling || !isOpen) return;
        try {
            const levelParam = levelFilter !== "all" ? `&level=${levelFilter}` : "";
            const res = await fetch(`/api/logs/file?lines=1000${levelParam}`).then(r => r.json());
            if (res.logs) setLogs(res.logs);
            if (res.stats) setStats(res.stats);
        } catch (e) { console.error(e); }
    }, [isPolling, isOpen, levelFilter]);

    useEffect(() => {
        if (isOpen) fetchLogs();
        const interval = setInterval(fetchLogs, 2000);
        return () => clearInterval(interval);
    }, [fetchLogs, isOpen]);

    useEffect(() => {
        if (autoScroll && bottomRef.current && isOpen) {
            bottomRef.current.scrollIntoView({ behavior: "smooth" });
        }
    }, [logs, autoScroll, isOpen]);

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
        link.download = `kafin_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.log`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const handleClear = async () => {
        await fetch("/api/logs/file", { method: "DELETE" });
        setLogs([]);
        setStats({ total: 0, error: 0, warning: 0, info: 0, ignore: 0 });
    };

    if (!isOpen) return null;

    const filteredLogs = logs.filter(l => l.toLowerCase().includes(searchTerm.toLowerCase()));
    const isIgnoreFilter = levelFilter === "ignore";

    const filterBtn = (level: LevelFilter, label: string, count: number, color: string, bgActive: string) => (
        <button
            onClick={() => setLevelFilter(levelFilter === level ? "all" : level)}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded font-mono text-xs transition-all ${
                levelFilter === level ? `${bgActive} ${color} ring-1 ring-current` : `bg-[var(--bg-secondary)] text-[var(--text-muted)] hover:${color}` 
            }`}
        >
            {level === "error" && <AlertCircle size={12} />}
            {level === "warning" && <AlertTriangle size={12} />}
            {level === "info" && <Info size={12} />}
            {level === "ignore" && <X size={12} />}
            {label}
            <span className="ml-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-black/20">{count}</span>
        </button>
    );

    return (
        <div className="fixed inset-x-0 bottom-0 h-[40vh] bg-[var(--bg-primary)] border-t border-[var(--border)] shadow-2xl shadow-black z-[100] flex flex-col font-mono transform transition-transform duration-300 translate-y-0">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2 bg-[var(--bg-secondary)] border-b border-[var(--border)]">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <Terminal size={16} className="text-[var(--accent-blue)]" />
                        <span className="text-[var(--accent-blue)] font-bold text-sm tracking-widest">KAFIN LOGS</span>
                    </div>
                    <div className="relative ml-4">
                        <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
                        <input type="text" placeholder="Grep..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} className="bg-[var(--bg-tertiary)] border border-[var(--border)] rounded px-7 py-1 text-xs text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent-blue)] w-48" />
                    </div>
                </div>
                <div className="flex items-center gap-3 text-xs text-[var(--text-muted)]">
                    <button onClick={() => setIsPolling(!isPolling)} className="flex items-center gap-1 hover:text-[var(--text-primary)] transition">{isPolling ? <Pause size={14}/> : <Play size={14}/>} {isPolling ? 'Pause' : 'Play'}</button>
                    <div className="w-px h-4 bg-[var(--border)]"></div>
                    <button onClick={handleClear} className="flex items-center gap-1 hover:text-rose-400 transition"><Trash2 size={14}/> Clear</button>
                    <button onClick={handleExport} className="flex items-center gap-1 hover:text-[var(--text-primary)] transition"><Download size={14}/> Export</button>
                    <div className="w-px h-4 bg-[var(--border)]"></div>
                    <button onClick={() => setIsOpen(false)} className="flex items-center gap-1 hover:text-white transition bg-[var(--bg-tertiary)] px-2 py-1 rounded"><X size={14}/> Schließen</button>
                </div>
            </div>

            {/* Filter Bar */}
            <div className="flex items-center gap-2 px-4 py-1.5 bg-[var(--bg-tertiary)] border-b border-[var(--border)]">
                <Filter size={12} className="text-[var(--text-muted)]" />
                <button onClick={() => setLevelFilter("all")} className={`px-2 py-1 rounded font-mono text-xs transition-all ${levelFilter === "all" ? "bg-[var(--bg-secondary)] text-white ring-1 ring-[var(--border)]" : "text-[var(--text-muted)] hover:text-white"}`}>Alle</button>
                {filterBtn("error", "Errors", stats.error, "text-rose-400", "bg-rose-950/40")}
                {filterBtn("warning", "Warnings", stats.warning, "text-amber-400", "bg-amber-950/40")}
                {filterBtn("info", "Info", stats.info, "text-blue-400", "bg-blue-950/40")}
                {filterBtn("ignore", "Ignore", stats.ignore, "text-slate-400", "bg-slate-950/40")}
                <div className="ml-auto text-[10px] text-[var(--text-muted)]">Zeilen: {filteredLogs.length} / {stats.total}</div>
            </div>

            {/* Log Output */}
            <div ref={containerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-3 space-y-px text-[12px] custom-scrollbar bg-[#0B0F1A]">
                {filteredLogs.map((log, i) => {
                    const l = log.toLowerCase();
                    const isErr = l.includes("[error]") || l.includes("error_code");
                    const isWarn = l.includes("[warning]");
                    const col = isIgnoreFilter
                      ? "text-slate-400 bg-slate-950/20"
                      : isErr
                      ? "text-rose-400 font-bold bg-rose-950/20"
                      : isWarn
                      ? "text-amber-400 bg-amber-950/10"
                      : "text-[var(--text-secondary)]";
                    return (
                        <div key={i} className={`flex gap-3 px-2 py-0.5 break-all whitespace-pre-wrap hover:bg-white/5 ${col}`}>
                            {isIgnoreFilter && <X size={13} className="mt-0.5 shrink-0" />}
                            {!isIgnoreFilter && isErr && <AlertCircle size={13} className="mt-0.5 shrink-0" />}
                            {isWarn && <AlertTriangle size={13} className="mt-0.5 shrink-0" />}
                            <span className="opacity-70">[{i+1}]</span> {log}
                        </div>
                    );
                })}
                <div ref={bottomRef} className="h-4" />
            </div>
        </div>
    );
}

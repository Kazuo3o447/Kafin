"use client";
import React, { useState, useEffect, useRef, useCallback } from "react";
import { Terminal, Download, Pause, Play, Trash2, Search, AlertTriangle } from "lucide-react";

export default function TerminalPage() {
    const [logs, setLogs] = useState<string[]>([]);
    const [isPolling, setIsPolling] = useState(true);
    const [autoScroll, setAutoScroll] = useState(true);
    const [searchTerm, setSearchTerm] = useState("");
    const bottomRef = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const fetchLogs = useCallback(async () => {
        if (!isPolling) return;
        try {
            const res = await fetch("/api/logs/file?lines=1000").then(r => r.json());
            if (res.logs) setLogs(res.logs);
        } catch (e) { console.error(e); }
    }, [isPolling]);

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
    };

    const filteredLogs = logs.filter(l => l.toLowerCase().includes(searchTerm.toLowerCase()));

    return (
        <div className="fixed inset-0 z-50 bg-[#0a0a0a] flex flex-col h-screen overflow-hidden">
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
                    <button onClick={() => setIsPolling(!isPolling)} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:bg-gray-700"><Pause size={14}/> {isPolling ? 'Pause' : 'Play'}</button>
                    <div className="px-3 py-1.5 rounded border border-gray-700">Auto-Scroll: {autoScroll ? 'ON' : 'OFF'}</div>
                    <button onClick={handleClear} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:text-red-400"><Trash2 size={14}/> Clear</button>
                    <button onClick={handleExport} className="flex items-center gap-1 px-3 py-1.5 rounded bg-gray-800 hover:text-white"><Download size={14}/> Export</button>
                </div>
            </div>
            <div ref={containerRef} onScroll={handleScroll} className="flex-1 overflow-y-auto p-4 space-y-px text-[13px]">
                {filteredLogs.map((log, i) => {
                    const l = log.toLowerCase();
                    const isErr = l.includes("[error]") || l.includes("error_code");
                    const isWarn = l.includes("[warning]");
                    const col = isErr ? "text-red-500 font-bold bg-red-950/20" : isWarn ? "text-yellow-400" : "text-green-400";
                    return (
                        <div key={i} className={`flex gap-3 px-2 py-0.5 font-mono break-all whitespace-pre-wrap hover:bg-white/5 ${col}`}>
                            {isErr && <AlertTriangle size={14} className="mt-0.5 shrink-0" />}
                            {log}
                        </div>
                    );
                })}
                <div ref={bottomRef} className="h-4" />
            </div>
        </div>
    );
}

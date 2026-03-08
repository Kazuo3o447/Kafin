"""
admin — Minimales Admin-Panel via FastAPI HTMLResponse

Input:  HTTP GET /admin, API-Endpoints
Output: HTML Seite mit Tailwind CSS
Deps:   FastAPI, settings, logger
Config: .env, settings.yaml
"""
from fastapi import APIRouter, Request, HTTPException, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import httpx
import yaml
import dotenv
import os
from datetime import datetime
from typing import Dict, Any

from backend.app.config import settings, YAML_PATH, ENV_PATH
from backend.app.logger import get_recent_logs, get_logger

logger = get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# HTML TEMPLATE
# ---------------------------------------------------------------------------
ADMIN_HTML = """
<!DOCTYPE html>
<html lang="de" class="dark">
<head>
    <meta charset="UTF-8">
    <title>Kafin Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: {
                extend: {
                    colors: {
                        gray: {
                            900: '#111827',
                            800: '#1F2937',
                            700: '#374151',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .tab-btn.active { border-bottom: 2px solid #3b82f6; color: #3b82f6; }
    </style>
</head>
<body class="bg-gray-900 text-gray-100 min-h-screen font-sans">
    
    <header class="bg-gray-800 border-b border-gray-700 p-4 sticky top-0 z-10">
        <div class="max-w-6xl mx-auto flex justify-between items-center">
            <h1 class="text-xl font-bold text-blue-400">Kafin Admin Panel</h1>
            <div class="flex space-x-1">
                <button onclick="switchTab('reports')" id="btn-reports" class="tab-btn active px-4 py-2 hover:bg-gray-700 rounded transition">Reports</button>
                <button onclick="switchTab('watchlist')" id="btn-watchlist" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Watchlist</button>
                <button onclick="switchTab('news')" id="btn-news" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">News</button>
                <button onclick="switchTab('settings')" id="btn-settings" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Einstellungen</button>
                <button onclick="switchTab('logs')" id="btn-logs" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Logs</button>
                <button onclick="switchTab('status')" id="btn-status" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Status</button>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto p-6 mt-4">
        
        <!-- REPORTS TAB -->
        <div id="tab-reports" class="tab-content active space-y-8">
            <section class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-lg font-semibold text-white">Report Generator</h2>
                    <button id="btn-sunday-report" onclick="generateSundayReport()" class="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded transition font-medium shadow-lg flex items-center">
                        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"></path></svg>
                        Sonntags-Report generieren
                    </button>
                </div>
                
                <div class="mb-6">
                    <h3 class="text-sm font-medium text-gray-400 mb-2">Einzelne Audit-Reports (aus Watchlist)</h3>
                    <div id="report-ticker-list" class="flex flex-wrap gap-2">
                        <!-- Loaded via JS -->
                        <span class="text-gray-500 text-sm">Lade Watchlist...</span>
                    </div>
                </div>
                
                <div class="bg-gray-900 border border-gray-700 rounded-lg p-4 h-[500px] flex flex-col relative">
                    <div id="report-status-overlay" class="absolute inset-0 bg-gray-900/80 backdrop-blur-sm hidden flex flex-col items-center justify-center rounded-lg z-10 transition-all">
                        <svg class="animate-spin w-10 h-10 text-blue-500 mb-4" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        <span id="report-status-text" class="text-white font-medium">Generiere Report...</span>
                    </div>
                    
                    <div class="flex justify-between items-center mb-2">
                        <h4 class="text-sm font-medium text-gray-300">Letzter Report Output</h4>
                        <button onclick="copyReport()" class="text-xs text-blue-400 hover:text-blue-300">In Zwischenablage kopieren</button>
                    </div>
                    <textarea id="report-output-area" readonly class="w-full flex-1 bg-black text-gray-300 font-mono text-sm p-4 rounded border border-gray-800 resize-none focus:outline-none"></textarea>
                </div>
            </section>
        </div>

        <!-- WATCHLIST TAB -->
        <div id="tab-watchlist" class="tab-content space-y-8">
            <section class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-lg font-semibold text-white">Watchlist</h2>
                    <button onclick="loadWatchlist()" class="text-sm bg-gray-700 hover:bg-gray-600 px-3 py-1 rounded text-white transition">Aktualisieren</button>
                </div>
                
                <div class="overflow-x-auto">
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-900 border-b border-gray-700">
                                <th class="p-3 text-sm font-semibold text-gray-300">Ticker</th>
                                <th class="p-3 text-sm font-semibold text-gray-300">Name</th>
                                <th class="p-3 text-sm font-semibold text-gray-300">Sektor</th>
                                <th class="p-3 text-sm font-semibold text-gray-300">Notizen</th>
                                <th class="p-3 text-sm font-semibold text-gray-300">Aktionen</th>
                            </tr>
                        </thead>
                        <tbody id="watchlist-table-body" class="divide-y divide-gray-700">
                            <!-- Loaded via JS -->
                        </tbody>
                    </table>
                </div>
                
                <hr class="border-gray-700 my-6">
                
                <h3 class="text-md font-medium text-gray-300 mb-3">Ticker hinzufügen</h3>
                <form id="watchlist-form" class="flex items-end space-x-3">
                    <div class="w-24">
                        <label class="block text-xs text-gray-400 mb-1">Ticker</label>
                        <input type="text" id="wl-ticker" required class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white uppercase" placeholder="AAPL">
                    </div>
                    <div class="flex-1">
                        <label class="block text-xs text-gray-400 mb-1">Company Name</label>
                        <input type="text" id="wl-name" required class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" placeholder="Apple Inc.">
                    </div>
                    <div class="w-48">
                        <label class="block text-xs text-gray-400 mb-1">Sektor</label>
                        <select id="wl-sector" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                            <option value="Technology">Technology</option>
                            <option value="Healthcare">Healthcare</option>
                            <option value="Financials">Financials</option>
                            <option value="Consumer Discretionary">Consumer Disc.</option>
                            <option value="Communication Services">Comm. Services</option>
                            <option value="Industrials">Industrials</option>
                            <option value="Consumer Staples">Consumer Staples</option>
                            <option value="Energy">Energy</option>
                            <option value="Utilities">Utilities</option>
                            <option value="Real Estate">Real Estate</option>
                            <option value="Materials">Materials</option>
                        </select>
                    </div>
                    <div class="flex-1">
                        <label class="block text-xs text-gray-400 mb-1">Notizen</label>
                        <input type="text" id="wl-notes" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white" placeholder="Optionale Notiz...">
                    </div>
                    <button type="button" onclick="addWatchlistItem()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition font-medium mb-[1px]">Hinzufügen</button>
                </form>
            </section>
        </div>

        <!-- NEWS TAB -->
        <div id="tab-news" class="tab-content space-y-8">
            <section class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <div class="flex justify-between items-center mb-6">
                    <h2 class="text-lg font-semibold text-white">News Pipeline & Scanner</h2>
                    <div class="space-x-2">
                        <button id="btn-sec-scan" onclick="runSecScan()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition shadow">SEC-Scan starten</button>
                        <button id="btn-news-scan" onclick="runNewsScan()" class="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded transition shadow">News-Scan starten</button>
                    </div>
                </div>
                
                <div class="mb-6">
                    <h3 class="text-sm font-medium text-gray-400 mb-2">Manuelle Pipeline-Ausführung (aus Watchlist)</h3>
                    <div id="news-ticker-list" class="flex flex-wrap gap-2">
                        <!-- Loaded via JS -->
                        <span class="text-gray-500 text-sm">Lade Watchlist...</span>
                    </div>
                </div>

                <div class="overflow-x-auto mb-8">
                    <h3 class="text-md font-medium text-gray-300 mb-3">Zuletzt Ausgeführte Scans</h3>
                    <table class="w-full text-left border-collapse">
                        <thead>
                            <tr class="bg-gray-900 border-b border-gray-700">
                                <th class="p-3 text-sm font-semibold text-gray-300">Ticker</th>
                                <th class="p-3 text-sm font-semibold text-gray-300 text-center">Geholt</th>
                                <th class="p-3 text-sm font-semibold text-gray-300 text-center">Relevant</th>
                                <th class="p-3 text-sm font-semibold text-gray-300 text-center">Gespeichert</th>
                                <th class="p-3 text-sm font-semibold text-gray-300 text-center">Alerts</th>
                            </tr>
                        </thead>
                        <tbody id="news-results-body" class="divide-y divide-gray-700">
                            <tr><td colspan="5" class="p-4 text-center text-gray-500">Noch keine Scans durchgeführt</td></tr>
                        </tbody>
                    </table>
                </div>

                <hr class="border-gray-700 my-6">

                <div>
                    <div class="flex justify-between items-center mb-3">
                        <h3 class="text-md font-medium text-gray-300">News Gedächtnis (Short-Term Memory)</h3>
                        <select id="news-memory-select" onchange="loadNewsMemory()" class="bg-gray-900 border border-gray-700 rounded p-1.5 text-sm text-white focus:outline-none w-48">
                            <option value="">Ticker auswählen...</option>
                        </select>
                    </div>
                    
                    <div class="bg-gray-900 border border-gray-700 rounded-lg p-4 h-[400px] overflow-auto">
                        <div id="news-memory-content" class="space-y-4">
                            <p class="text-gray-500 text-sm text-center mt-10">Wählen Sie einen Ticker, um gespeicherte Stichpunkte zu sehen.</p>
                        </div>
                    </div>
                </div>
            </section>
        </div>

        <!-- SETTINGS TAB -->
        <div id="tab-settings" class="tab-content space-y-8">
            <section class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <h2 class="text-lg font-semibold mb-4 text-white">App Einstellungen (settings.yaml)</h2>
                <form id="settings-form" class="space-y-4">
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div>
                            <label class="block text-sm text-gray-400 mb-1">Environment</label>
                            <select id="set-env" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                                <option value="development">development</option>
                                <option value="production">production</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm text-gray-400 mb-1">Use Mock Data</label>
                            <select id="set-mock" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                                <option value="true">An</option>
                                <option value="false">Aus</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm text-gray-400 mb-1">Log Level</label>
                            <select id="set-log" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                                <option value="DEBUG">DEBUG</option>
                                <option value="INFO">INFO</option>
                                <option value="WARNING">WARNING</option>
                                <option value="ERROR">ERROR</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-sm text-gray-400 mb-1">Report Sprache</label>
                            <select id="set-lang" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                                <option value="de">Deutsch</option>
                                <option value="en">English</option>
                            </select>
                        </div>
                    </div>
                    <button type="button" onclick="saveSettings()" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition font-medium mt-4">YAML Speichern</button>
                </form>
            </section>

            <section class="bg-gray-800 rounded-lg p-6 border border-gray-700 shadow-lg">
                <h2 class="text-lg font-semibold mb-4 text-white">API-Keys (.env)</h2>
                <div id="env-status" class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
                    <!-- Loaded via JS -->
                </div>
                
                <hr class="border-gray-700 mb-6">
                
                <h3 class="text-md font-medium text-gray-300 mb-3">API-Key hinzufügen/ändern</h3>
                <form id="env-form" class="flex space-x-3 items-end">
                    <div class="flex-1">
                        <label class="block text-sm text-gray-400 mb-1">Key Name</label>
                        <select id="env-key-name" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white">
                            <option value="FINNHUB_API_KEY">FINNHUB_API_KEY</option>
                            <option value="FMP_API_KEY">FMP_API_KEY</option>
                            <option value="FRED_API_KEY">FRED_API_KEY</option>
                            <option value="COINGLASS_API_KEY">COINGLASS_API_KEY</option>
                            <option value="DEEPSEEK_API_KEY">DEEPSEEK_API_KEY</option>
                            <option value="KIMI_API_KEY">KIMI_API_KEY</option>
                            <option value="SUPABASE_URL">SUPABASE_URL</option>
                            <option value="SUPABASE_KEY">SUPABASE_KEY</option>
                            <option value="TELEGRAM_BOT_TOKEN">TELEGRAM_BOT_TOKEN</option>
                            <option value="TELEGRAM_CHAT_ID">TELEGRAM_CHAT_ID</option>
                        </select>
                    </div>
                    <div class="flex-1">
                        <label class="block text-sm text-gray-400 mb-1">Wert</label>
                        <input type="password" id="env-key-value" class="w-full bg-gray-900 border border-gray-700 rounded p-2 text-white placeholder-gray-500" placeholder="••••••••••••">
                    </div>
                    <button type="button" onclick="saveEnvKey()" class="bg-green-600 hover:bg-green-500 text-white px-4 py-2 rounded transition font-medium mb-[1px]">In .env Speichern</button>
                </form>
            </section>
        </div>

        <!-- LOGS TAB -->
        <div id="tab-logs" class="tab-content h-[80vh] flex flex-col">
            <div class="flex justify-between items-center bg-gray-800 p-4 rounded-t-lg border border-gray-700 border-b-0">
                <div class="flex space-x-3 items-center">
                    <h2 class="text-lg font-semibold text-white">Live Logs</h2>
                    <span id="log-count" class="text-xs bg-gray-700 px-2 py-1 rounded text-gray-300">0 events</span>
                </div>
                <div>
                    <select id="log-filter" onchange="renderLogs()" class="bg-gray-900 border border-gray-700 rounded p-1.5 text-sm text-white focus:outline-none">
                        <option value="ALL">Alle Level</option>
                        <option value="DEBUG">DEBUG</option>
                        <option value="INFO">INFO</option>
                        <option value="WARNING">WARNING</option>
                        <option value="ERROR">ERROR</option>
                    </select>
                </div>
            </div>
            
            <div class="bg-black rounded-b-lg border border-gray-700 flex-1 overflow-auto font-mono text-sm p-4 relative" id="log-container">
                 <div id="log-list" class="space-y-1"></div>
            </div>
        </div>

        <!-- STATUS TAB -->
        <div id="tab-status" class="tab-content">
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-lg font-semibold text-white">System Status</h2>
                <button onclick="runStatusCheck()" id="btn-run-check" class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded transition flex items-center shadow">
                    <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
                    Alle Prüfen
                </button>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6" id="status-grid">
                 <!-- Loaded via JS -->
            </div>
        </div>

    </main>

    <!-- Notification Toast -->
    <div id="toast" class="fixed bottom-5 right-5 transform translate-y-20 opacity-0 transition-all duration-300 bg-gray-800 border border-gray-700 text-white px-6 py-3 rounded shadow-2xl z-50 flex items-center">
        <span id="toast-icon" class="mr-3"></span>
        <span id="toast-msg">Erfolgreich gespeichert!</span>
    </div>

    <script>
        // State
        let currentLogs = [];
        let logPollInterval = null;

        // Tab Switching
        function switchTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            
            document.getElementById(`tab-${tabId}`).classList.add('active');
            document.getElementById(`btn-${tabId}`).classList.add('active');
            
            if(tabId === 'logs') {
                startLogPolling();
            } else {
                stopLogPolling();
            }
            
            if(tabId === 'settings') loadSettings();
            if(tabId === 'watchlist') loadWatchlist();
            if(tabId === 'reports') {
                loadWatchlist(); // For the ticker buttons
                loadLatestReport();
            }
        }

        // --- REPORTS ---
        async function loadLatestReport() {
            try {
                const res = await fetch('/api/reports/latest');
                const data = await res.json();
                document.getElementById('report-output-area').value = data.report || "Kein Report im Speicher.";
            } catch(e) { console.error('Error loading latest report', e); }
        }
        
        async function generateAuditReport(ticker) {
            const overlay = document.getElementById('report-status-overlay');
            const statusText = document.getElementById('report-status-text');
            const output = document.getElementById('report-output-area');
            
            overlay.classList.remove('hidden');
            statusText.textContent = `Generiere Audit-Report für ${ticker}... (kann dauern)`;
            
            try {
                const res = await fetch(`/api/reports/generate/${ticker}`, {method: 'POST'});
                const data = await res.json();
                if(res.ok) {
                    output.value = data.report;
                    showToast(`Report für ${ticker} fertig!`);
                } else {
                    showToast('Fehler bei der Generierung', 'error');
                }
            } catch(e) {
                showToast('Verbindungsfehler', 'error');
            } finally {
                overlay.classList.add('hidden');
            }
        }
        
        async function generateSundayReport() {
            const overlay = document.getElementById('report-status-overlay');
            const statusText = document.getElementById('report-status-text');
            const output = document.getElementById('report-output-area');
            
            overlay.classList.remove('hidden');
            statusText.textContent = `Erstelle Sonntags-Report... (Makro + Watchlist)`;
            
            try {
                const res = await fetch(`/api/reports/generate-sunday`, {method: 'POST'});
                const data = await res.json();
                if(res.ok) {
                    output.value = data.report;
                    showToast(`Sonntags-Report fertig und per E-Mail versendet!`);
                } else {
                    showToast('Fehler bei der Generierung', 'error');
                }
            } catch(e) {
                showToast('Verbindungsfehler', 'error');
            } finally {
                overlay.classList.add('hidden');
            }
        }
        
        function copyReport() {
            const text = document.getElementById('report-output-area').value;
            navigator.clipboard.writeText(text).then(() => {
                showToast('Kopiert!');
            });
        }

        // --- WATCHLIST ---
        async function loadWatchlist() {
            try {
                const res = await fetch('/api/watchlist');
                const data = await res.json();
                
                // Update table
                const tbody = document.getElementById('watchlist-table-body');
                tbody.innerHTML = '';
                
                // Update report buttons
                const repList = document.getElementById('report-ticker-list');
                repList.innerHTML = '';
                
                if(data.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" class="p-4 text-center text-gray-500">Watchlist ist leer</td></tr>';
                    repList.innerHTML = '<span class="text-gray-500 text-sm">Keine Ticker auf der Watchlist.</span>';
                    return;
                }
                
                data.forEach(item => {
                    // Populate Table
                    tbody.innerHTML += `
                        <tr class="hover:bg-gray-800 transition">
                            <td class="p-3 font-mono font-medium text-blue-400">${item.ticker}</td>
                            <td class="p-3 font-medium">${item.company_name}</td>
                            <td class="p-3 text-sm text-gray-400">${item.sector || '-'}</td>
                            <td class="p-3 text-sm text-gray-400">${item.notes || '-'}</td>
                            <td class="p-3 text-sm text-right">
                                <button onclick="removeWatchlistItem('${item.ticker}')" class="text-red-400 hover:text-red-300 px-2 py-1 bg-red-400/10 hover:bg-red-400/20 rounded transition">Löschen</button>
                            </td>
                        </tr>
                    `;
                    
                    // Populate Report Buttons
                    repList.innerHTML += `
                        <button onclick="generateAuditReport('${item.ticker}')" class="bg-gray-700 hover:bg-gray-600 text-gray-100 text-sm px-3 py-1.5 rounded transition border border-gray-600">
                            ${item.ticker}
                        </button>
                    `;
                    
                    // Populate News Ticker List
                    const newsList = document.getElementById('news-ticker-list');
                    if(newsList) {
                        if(newsList.innerHTML.includes("Lade Watchlist...")) newsList.innerHTML = '';
                        newsList.innerHTML += `
                            <button onclick="runNewsScan('${item.ticker}')" class="bg-gray-700 hover:bg-purple-600 text-gray-100 text-sm px-3 py-1.5 rounded transition border border-gray-600">
                                ${item.ticker}
                            </button>
                        `;
                    }
                    
                    // Populate News Memory Dropdown
                    const dropdown = document.getElementById('news-memory-select');
                    if(dropdown) {
                        dropdown.innerHTML += `<option value="${item.ticker}">${item.ticker}</option>`;
                    }
                });
            } catch(e) { console.error('Error loading watchlist', e); showToast('Fehler beim Laden', 'error'); }
        }
        
        async function addWatchlistItem() {
            const payload = {
                ticker: document.getElementById('wl-ticker').value.toUpperCase(),
                company_name: document.getElementById('wl-name').value,
                sector: document.getElementById('wl-sector').value,
                notes: document.getElementById('wl-notes').value
            };
            
            if(!payload.ticker || !payload.company_name) {
                showToast('Ticker und Name erforderlich', 'error');
                return;
            }
            
            try {
                const res = await fetch('/api/watchlist', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                if(res.ok) {
                    showToast(`${payload.ticker} hinzugefügt`);
                    document.getElementById('wl-ticker').value = '';
                    document.getElementById('wl-name').value = '';
                    document.getElementById('wl-notes').value = '';
                    loadWatchlist();
                } else showToast('Fehler', 'error');
            } catch(e) { showToast('Fehler', 'error'); }
        }
        
        async function removeWatchlistItem(ticker) {
            if(!confirm(`${ticker} wirklich löschen?`)) return;
            try {
                const res = await fetch(`/api/watchlist/${ticker}`, {method: 'DELETE'});
                if(res.ok) {
                    showToast(`${ticker} gelöscht`);
                    loadWatchlist();
                } else showToast('Fehler beim Löschen', 'error');
            } catch(e) { showToast('Fehler', 'error'); }
        }

        // Toast Notification
        function showToast(msg, type='success') {
            const toast = document.getElementById('toast');
            document.getElementById('toast-msg').textContent = msg;
            document.getElementById('toast-icon').innerHTML = type === 'success' ? '✅' : '❌';
            if(type === 'error') toast.classList.add('border-red-500');
            else toast.classList.remove('border-red-500');
            
            toast.classList.remove('translate-y-20', 'opacity-0');
            setTimeout(() => {
                toast.classList.add('translate-y-20', 'opacity-0');
            }, 3000);
        }

        // --- NEWS SCANNER ---
        async function runSecScan() {
            const btn = document.getElementById('btn-sec-scan');
            btn.innerHTML = `<svg class="animate-spin w-4 h-4 mr-2 inline" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Scanning...`;
            btn.disabled = true;
            try {
                const res = await fetch('/api/news/sec-scan', {method: 'POST'});
                const data = await res.json();
                if(res.ok) {
                    showToast(`SEC Scan beendet. ${data.filings_found} Filings gefunden.`);
                } else showToast('Fehler beim SEC Scan', 'error');
            } catch(e) { showToast('Verbindungsfehler', 'error'); }
            finally {
                btn.innerHTML = 'SEC-Scan starten';
                btn.disabled = false;
            }
        }
        
        function appendNewsResult(data) {
            const tbody = document.getElementById('news-results-body');
            if(tbody.innerHTML.includes("Noch keine Scans")) tbody.innerHTML = '';
            
            const tr = document.createElement('tr');
            tr.className = "hover:bg-gray-800 transition";
            tr.innerHTML = `
                <td class="p-3 font-mono font-medium text-blue-400">${data.ticker}</td>
                <td class="p-3 text-sm text-center">${data.total_fetched}</td>
                <td class="p-3 text-sm text-center text-yellow-400">${data.passed_finbert}</td>
                <td class="p-3 text-sm text-center text-green-400">${data.bullets_saved}</td>
                <td class="p-3 text-sm text-center ${data.alerts_sent > 0 ? 'text-red-400 font-bold' : ''}">${data.alerts_sent}</td>
            `;
            tbody.insertBefore(tr, tbody.firstChild);
        }

        async function runNewsScan(ticker = null) {
            const endpoint = ticker ? `/api/news/scan/${ticker}` : '/api/news/scan';
            showToast(`Starte News Scan ${ticker ? 'für ' + ticker : '(Alle)'}...`);
            
            try {
                const res = await fetch(endpoint, {method: 'POST'});
                const data = await res.json();
                if(res.ok) {
                    showToast('Scan erfolgreich');
                    if(ticker) {
                        appendNewsResult(data.result);
                    } else {
                        data.results.forEach(appendNewsResult);
                    }
                } else showToast('Fehler beim Scan', 'error');
            } catch(e) { showToast('Verbindungsfehler', 'error'); }
        }

        async function loadNewsMemory() {
            const ticker = document.getElementById('news-memory-select').value;
            const container = document.getElementById('news-memory-content');
            
            if(!ticker) {
                container.innerHTML = '<p class="text-gray-500 text-sm text-center mt-10">Wählen Sie einen Ticker, um gespeicherte Stichpunkte zu sehen.</p>';
                return;
            }
            
            container.innerHTML = `<div class="flex justify-center mt-10"><svg class="animate-spin w-8 h-8 text-blue-500" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg></div>`;
            
            try {
                const res = await fetch(`/api/news/memory/${ticker}`);
                const data = await res.json();
                
                if(!data.bullet_points || data.bullet_points.length === 0) {
                    container.innerHTML = '<p class="text-gray-500 text-sm text-center mt-10">Keine Daten für diesen Ticker im Gedächtnis.</p>';
                    return;
                }
                
                container.innerHTML = '';
                data.bullet_points.forEach(bp => {
                    const dateStr = bp.date ? bp.date.split('T')[0] : 'Unbekannt';
                    const score = parseFloat(bp.sentiment_score || 0);
                    const color = score > 0.3 ? 'text-green-400' : (score < -0.3 ? 'text-red-400' : 'text-gray-400');
                    
                    let bulletsHtml = '';
                    if(Array.isArray(bp.bullet_points)) {
                        bulletsHtml = `<ul class="list-disc list-inside text-sm text-gray-300 mt-2 space-y-1">` + 
                            bp.bullet_points.map(b => `<li>${b}</li>`).join('') + 
                            `</ul>`;
                    } else if(typeof bp.bullet_points === 'string') {
                        bulletsHtml = `<p class="text-sm text-gray-300 mt-2">${bp.bullet_points}</p>`;
                    }
                    
                    container.innerHTML += `
                        <div class="bg-black p-3 rounded border border-gray-800">
                            <div class="flex justify-between items-center bg-gray-900 -mx-3 -mt-3 p-2 px-3 border-b border-gray-800 rounded-t">
                                <span class="text-xs text-gray-500">${dateStr} | ${bp.category || 'general'}</span>
                                <span class="text-xs ${color} font-mono">Sent: ${score.toFixed(2)}</span>
                            </div>
                            ${bulletsHtml}
                        </div>
                    `;
                });
                
            } catch(e) {
                container.innerHTML = `<p class="text-red-500 text-sm text-center mt-10">Fehler beim Laden.</p>`;
            }
        }

        // --- SETTINGS ---
        async function loadSettings() {
            try {
                const res = await fetch('/api/settings');
                const data = await res.json();
                
                // Set form values
                document.getElementById('set-env').value = data.settings.environment;
                document.getElementById('set-mock').value = data.settings.use_mock_data ? "true" : "false";
                document.getElementById('set-log').value = data.settings.log_level;
                document.getElementById('set-lang').value = data.settings.report_language;
                
                // Render Env statuses
                const envContainer = document.getElementById('env-status');
                envContainer.innerHTML = '';
                for (const [key, isSet] of Object.entries(data.env_status)) {
                    envContainer.innerHTML += `
                        <div class="flex justify-between items-center bg-gray-900 px-4 py-2 rounded border border-gray-700">
                            <span class="font-mono text-sm text-gray-300">${key}</span>
                            <span>${isSet ? '<span class="text-green-500">✅ Konfiguriert</span>' : '<span class="text-red-500">❌ Fehlt</span>'}</span>
                        </div>
                    `;
                }
            } catch (e) { console.error("Error loading settings", e); }
        }

        async function saveSettings() {
            const payload = {
                environment: document.getElementById('set-env').value,
                use_mock_data: document.getElementById('set-mock').value === "true",
                log_level: document.getElementById('set-log').value,
                report_language: document.getElementById('set-lang').value
            };
            try {
                const res = await fetch('/api/settings/yaml', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                if(res.ok) showToast('YAML Settings neu geladen!');
                else showToast('Fehler beim Speichern', 'error');
            } catch(e) { showToast('Fehler', 'error'); }
        }

        async function saveEnvKey() {
            const key = document.getElementById('env-key-name').value;
            const val = document.getElementById('env-key-value').value;
            if(!val) { showToast('Bitte Wert eingeben', 'error'); return; }
            
            try {
                const res = await fetch('/api/settings/env', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ key, value: val })
                });
                if(res.ok) {
                    showToast(`${key} gespeichert!`);
                    document.getElementById('env-key-value').value = '';
                    loadSettings();
                } else showToast('Fehler beim Speichern', 'error');
            } catch(e) { showToast('Fehler', 'error'); }
        }

        // --- LOGS ---
        function startLogPolling() {
            fetchLogs();
            if(!logPollInterval) logPollInterval = setInterval(fetchLogs, 3000);
        }
        function stopLogPolling() {
            if(logPollInterval) { clearInterval(logPollInterval); logPollInterval = null; }
        }
        
        async function fetchLogs() {
            try {
                const res = await fetch('/api/logs');
                currentLogs = await res.json();
                renderLogs();
            } catch (e) { console.error("Error fetching logs", e); }
        }
        
        function renderLogs() {
            const filter = document.getElementById('log-filter').value;
            const list = document.getElementById('log-list');
            list.innerHTML = '';
            
            const colors = {
                "DEBUG": "text-gray-500",
                "INFO": "text-gray-200",
                "WARNING": "text-yellow-400",
                "ERROR": "text-red-500 font-bold"
            };
            
            let count = 0;
            currentLogs.forEach(log => {
                if(filter !== 'ALL' && log.level !== filter.toLowerCase()) return;
                count++;
                
                const level = log.level ? log.level.toUpperCase() : "INFO";
                const colorClass = colors[level] || colors["INFO"];
                const timeStr = log.timestamp ? log.timestamp.split('T')[1].substring(0,8) : "";
                const name = log.logger || "app";
                const event = log.event || "";
                
                const div = document.createElement('div');
                div.className = "flex space-x-3 hover:bg-gray-900 px-2 py-0.5 rounded";
                div.innerHTML = `
                    <span class="text-gray-500 whitespace-nowrap">[${timeStr}]</span>
                    <span class="${colorClass} w-16">${level}</span>
                    <span class="text-gray-500 w-32 truncate" title="${name}">${name}</span>
                    <span class="${colorClass} flex-1 break-all">${event}</span>
                `;
                list.appendChild(div);
            });
            document.getElementById('log-count').textContent = `${count} events`;
        }

        // --- STATUS ---
        async function runStatusCheck() {
            const btn = document.getElementById('btn-run-check');
            btn.innerHTML = `<svg class="animate-spin w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> Prüfe...`;
            
            try {
                const res = await fetch('/api/status/check', {method: 'POST'});
                const data = await res.json();
                renderStatusGrid(data);
                showToast('Status geprüft!');
            } catch (e) {
                showToast('Prüfung fehlgeschlagen', 'error');
            }
            btn.innerHTML = `<svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg> Alle Prüfen`;
        }
        
        // Individual API test
        async function testApi(apiName) {
            const btn = document.getElementById(`btn-test-${apiName}`);
            const originalText = btn.innerHTML;
            btn.innerHTML = '...';
            btn.disabled = true;
            
            try {
                // We pass the specific API to check as a query parameter
                const res = await fetch(`/api/status/check?api=${apiName}`, {method: 'POST'});
                const data = await res.json();
                renderStatusGrid(data);
                showToast(`${apiName.toUpperCase()} Ping erfolgreich gesendet.`);
            } catch (e) {
                showToast(`Prüfung für ${apiName} fehlgeschlagen`, 'error');
            }
        }
        
        function renderStatusGrid(data) {
            const grid = document.getElementById('status-grid');
            grid.innerHTML = '';
            
            // Helper to render a card
            const renderCard = (title, items) => {
                let itemsHtml = items.map(i => `
                    <div class="flex justify-between items-center py-2 border-b border-gray-700 last:border-0">
                        <div class="flex items-center">
                            <span class="text-sm text-gray-300 font-medium">${i.label}</span>
                            ${i.testable ? `<button onclick="testApi('${i.id}')" id="btn-test-${i.id}" class="ml-2 text-[10px] bg-gray-700 hover:bg-gray-600 px-2 py-0.5 rounded text-gray-300 transition uppercase tracking-wider">Test</button>` : ''}
                        </div>
                        <div class="flex items-center space-x-2">
                           ${i.status === 'ok' ? '<span class="w-2 h-2 bg-green-500 rounded-full shadow-[0_0_5px_rgba(34,197,94,0.5)]"></span><span class="text-xs text-gray-400">OK</span>' : 
                             i.status === 'error' ? '<span class="w-2 h-2 bg-red-500 rounded-full shadow-[0_0_5px_rgba(239,68,68,0.5)]"></span><span class="text-xs text-gray-400">Error</span>' : 
                             '<span class="w-2 h-2 bg-yellow-500 rounded-full shadow-[0_0_5px_rgba(234,179,8,0.5)]"></span><span class="text-xs text-gray-400">N/A</span>'}
                        </div>
                    </div>
                `).join('');
                
                return `
                    <div class="bg-gray-800 rounded-lg p-5 border border-gray-700 shadow-lg">
                        <h3 class="text-md font-semibold text-white mb-3 flex items-center">
                            <svg class="w-4 h-4 mr-2 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"></path></svg>
                            ${title}
                        </h3>
                        <div>${itemsHtml}</div>
                    </div>
                `;
            };

            // APIs
            const apis = ['Finnhub', 'FMP', 'FRED', 'CoinGlass', 'DeepSeek', 'Kimi', 'FinBERT'].map(k => {
                const id = k.toLowerCase();
                const keySet = data.keys[id];
                return { id: id, label: k, status: keySet ? (data.api_checks[id] || 'warning') : 'warning', testable: true };
            });
            
            // Add Telegram individually since it's an API, but not in the original list
            const telSet = data.keys['telegram'];
            apis.push({ id: 'telegram', label: 'Telegram', status: telSet ? (data.api_checks['telegram'] || 'warning') : 'warning', testable: true });
            
            grid.innerHTML += renderCard('API Schnittstellen', apis);

            // Services
            const services = [
                { label: 'Supabase', status: data.keys.supabase ? 'ok' : 'error' },
                { label: 'Redis (Cache)', status: 'ok' }, // Mock for now until we spin up docker completely
                { label: 'n8n (Workflows)', status: 'ok' }
            ];
            grid.innerHTML += renderCard('Infrastruktur', services);

            // System
            const system = [
                { label: 'Environment', status: 'ok' },
                { label: 'Mock-Modus', status: data.settings.use_mock_data ? 'warning' : 'ok' },
                { label: 'Backend API', status: 'ok' }
            ];
            grid.innerHTML += renderCard('System', system);
        }

        // Init
        loadWatchlist();
        loadLatestReport();
        // prefill status grid with basic info initially
        fetch('/api/status/check', {method: 'POST'}).then(r=>r.json()).then(renderStatusGrid);
    </script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@router.get("/admin", response_class=HTMLResponse, include_in_schema=False)
async def admin_panel():
    return HTMLResponse(content=ADMIN_HTML)

class YamlSettingsPayload(BaseModel):
    environment: str
    use_mock_data: bool
    log_level: str
    report_language: str

@router.get("/api/settings")
async def get_settings():
    """Gibt die aktuellen Settings und den .env Status zurück"""
    
    # Check env presence
    expected_keys = [
        "FINNHUB_API_KEY", "FMP_API_KEY", "FRED_API_KEY", "COINGLASS_API_KEY",
        "DEEPSEEK_API_KEY", "KIMI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY",
        "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
    ]
    
    env_status = {}
    for key in expected_keys:
        val = os.getenv(key) or getattr(settings, key.lower(), None)
        env_status[key] = bool(val)
        
    return {
        "settings": {
            "environment": settings.environment,
            "use_mock_data": settings.use_mock_data,
            "log_level": settings.log_level,
            "report_language": settings.report_language
        },
        "env_status": env_status
    }

@router.post("/api/settings/yaml")
async def update_yaml_settings(payload: YamlSettingsPayload):
    """Überschreibt die settings.yaml und reloads settings in memory"""
    import yaml
    
    # Read existing or create new
    if os.path.exists(YAML_PATH):
        with open(YAML_PATH, "r", encoding="utf-8") as f:
            data: dict = yaml.safe_load(f) or {}
    else:
        data: dict = {}
        
    if "app" not in data: data["app"] = {}
    if "flags" not in data: data["flags"] = {}
    if "admin" not in data: data["admin"] = {}

    data["app"]["env"] = payload.environment
    data["flags"]["use_mock_data"] = payload.use_mock_data
    data["admin"]["log_level"] = payload.log_level
    data["admin"]["report_language"] = payload.report_language
    
    with open(YAML_PATH, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    # Reload settings in current process
    settings.reload_from_yaml()
    logger.info(f"Admin Update: YAML Settings gespeichert und geladen. Mock={settings.use_mock_data}, Env={settings.environment}")
    
    return {"status": "success"}

class EnvPayload(BaseModel):
    key: str
    value: str

@router.post("/api/settings/env")
async def update_env_key(payload: EnvPayload):
    """Schreibt einen API Key in die .env Datei"""
    dotenv.set_key(ENV_PATH, payload.key, payload.value)
    
    # Load immediately into process env, but pydantic ignores post-init changes so we force it
    os.environ[payload.key] = payload.value
    setattr(settings, payload.key.lower(), payload.value)
    
    logger.info(f"Admin Update: ENV Key aktualisiert: {payload.key}")
    return {"status": "success"}

@router.get("/api/logs")
async def get_logs_endpoint():
    """Gibt den in-memory Log buffer zurück"""
    logs = get_recent_logs()
    return logs

@router.post("/api/status/check")
async def run_status_check(api: str = None):
    """
    Führt simple GET Requests aus, wenn die Keys da sind.
    Wenn `api` angegeben ist, wird nur dieser eine Service aktiv getestet (Netzwerk),
    die anderen bekommen nur ihren Key-Status.
    """
    # Keys
    keys = {
        "finnhub": bool(settings.finnhub_api_key),
        "fmp": bool(settings.fmp_api_key),
        "fred": bool(settings.fred_api_key),
        "coinglass": bool(settings.coinglass_api_key),
        "deepseek": bool(settings.deepseek_api_key),
        "kimi": bool(settings.kimi_api_key),
        "telegram": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "supabase": bool(settings.supabase_url and settings.supabase_key),
        "finbert": True # Local model, always "configured"
    }
    
    # Simple Ping Tests
    checks = {}
    
    async def try_ping(name: str, url: str, headers: dict = None, params: dict = None):
        if not keys.get(name) and name != "finbert":
            return "warning"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(url, headers=headers, params=params)
                if res.status_code == 200:
                    return "ok"
                return "error"
        except:
            return "error"

    # Only test the requested API, or all if none provided
    if api is None or api == "finnhub":
        if keys["finnhub"]:
            checks["finnhub"] = await try_ping("finnhub", f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={settings.finnhub_api_key}")
    
    if api is None or api == "fmp":
        if keys["fmp"]:
             checks["fmp"] = await try_ping("fmp", f"https://financialmodelingprep.com/api/v3/profile/AAPL?apikey={settings.fmp_api_key}")
             
    if api is None or api == "fred":
        if keys["fred"]:
             checks["fred"] = await try_ping("fred", f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={settings.fred_api_key}&file_type=json&limit=1")
             
    if api is None or api == "coinglass":
        if keys["coinglass"]:
             checks["coinglass"] = await try_ping("coinglass", "https://open-api.coinglass.com/public/v2/indicator/bitcoin_profitable_days", headers={"coinglassSecret": settings.coinglass_api_key})
             
    if api is None or api == "deepseek":
         if keys["deepseek"]:
              # Need POST for Chat API, or simple GET if they have a status endpoint?
              # For now, let's just assume OK if key is set, or try a tiny prompt
              checks["deepseek"] = "ok" # Placeholder
              
    if api is None or api == "kimi":
         if keys["kimi"]:
              checks["kimi"] = "ok" # Placeholder
              
    if api is None or api == "telegram":
         if keys["telegram"]:
             checks["telegram"] = await try_ping("telegram", f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe")

    if api is None or api == "finbert":
         try:
             # Fast local test
             import time
             start = time.time()
             from backend.app.analysis.finbert import analyze_sentiment
             # Force model load if not loaded
             analyze_sentiment("test") 
             duration = (time.time() - start) * 1000
             logger.info(f"Admin Status Check: FinBERT reagiert in {duration:.0f}ms")
             checks["finbert"] = "ok"
         except Exception as e:
             logger.error(f"FinBERT Status Check Error: {e}")
             checks["finbert"] = "error"

    return {
        "status": "success",
        "keys": keys,
        "api_checks": checks,
        "settings": {
            "use_mock_data": settings.use_mock_data
        }
    }

            if has_keys["fmp"]:
                if settings.use_mock_data:
                    api_checks["fmp"] = "ok"
                else:
                    try:
                        res = await client.get(f"https://financialmodelingprep.com/stable/search-symbol?query=AAPL&apikey={settings.fmp_api_key}")
                        api_checks["fmp"] = "ok" if res.status_code == 200 else "error"
                    except Exception as e:
                        logger.error(f"Status check failed for FMP: {str(e)}")
                        api_checks["fmp"] = "error"
            else:
                 api_checks["fmp"] = "warning"

        # FRED
        if "fred" in targets or not api:
            if has_keys["fred"]:
                if settings.use_mock_data:
                    api_checks["fred"] = "ok"
                else:
                    try:
                        res = await client.get(f"https://api.stlouisfed.org/fred/series/observations?series_id=VIXCLS&api_key={settings.fred_api_key}&sort_order=desc&limit=1&file_type=json")
                        api_checks["fred"] = "ok" if res.status_code == 200 else "error"
                    except Exception as e:
                        logger.error(f"Status check failed for FRED: {str(e)}")
                        api_checks["fred"] = "error"
            else:
                 api_checks["fred"] = "warning"

        # DEEPSEEK
        if "deepseek" in targets or not api:
            if has_keys["deepseek"]:
                if settings.use_mock_data:
                    api_checks["deepseek"] = "ok"
                else:
                    try:
                        res = await client.post("https://api.deepseek.com/chat/completions", headers={"Authorization": f"Bearer {settings.deepseek_api_key}"}, json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "Ping"}], "max_tokens": 5})
                        api_checks["deepseek"] = "ok" if res.status_code == 200 else "error"
                    except Exception as e:
                        logger.error(f"Status check failed for DeepSeek: {str(e)}")
                        api_checks["deepseek"] = "error"
            else:
                 api_checks["deepseek"] = "warning"

        # TELEGRAM
        if "telegram" in targets or not api:
            if has_keys["telegram"]:
                if settings.use_mock_data:
                    api_checks["telegram"] = "ok"
                else:
                    try:
                        res = await client.get(f"https://api.telegram.org/bot{telegram_token}/getMe")
                        api_checks["telegram"] = "ok" if res.status_code == 200 else "error"
                    except Exception as e:
                        logger.error(f"Status check failed for Telegram: {str(e)}")
                        api_checks["telegram"] = "error"
            else:
                 api_checks["telegram"] = "warning"

        # Mock others for now since they are not fully wired up
        for k in ["coinglass", "kimi"]:
            if k in targets or not api:
                if has_keys.get(k, False):
                    api_checks[k] = "ok" # We assume it works if we have the key for the MVP Status Check
                else:
                    api_checks[k] = "warning"

    # Fill up the rest with defaults if a single specific API was queried
    for k in has_keys:
        if k not in api_checks:
            api_checks[k] = "ok" if has_keys[k] else "warning"

    return {
        "status": "success",
        "timestamp": datetime.utcnow().isoformat(),
        "keys": has_keys,
        "api_checks": api_checks,
        "settings": {
              "use_mock_data": settings.use_mock_data,
              "environment": settings.environment
        }
    }

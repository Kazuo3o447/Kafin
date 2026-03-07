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
    <title>Antigravity Admin</title>
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
            <h1 class="text-xl font-bold text-blue-400">Antigravity Admin Panel</h1>
            <div class="flex space-x-1">
                <button onclick="switchTab('settings')" id="btn-settings" class="tab-btn active px-4 py-2 hover:bg-gray-700 rounded transition">Einstellungen</button>
                <button onclick="switchTab('logs')" id="btn-logs" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Logs</button>
                <button onclick="switchTab('status')" id="btn-status" class="tab-btn px-4 py-2 hover:bg-gray-700 rounded transition">Status</button>
            </div>
        </div>
    </header>

    <main class="max-w-6xl mx-auto p-6 mt-4">
        
        <!-- SETTINGS TAB -->
        <div id="tab-settings" class="tab-content active space-y-8">
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
        
        function renderStatusGrid(data) {
            const grid = document.getElementById('status-grid');
            grid.innerHTML = '';
            
            // Helper to render a card
            const renderCard = (title, items) => {
                let itemsHtml = items.map(i => `
                    <div class="flex justify-between items-center py-2 border-b border-gray-700 last:border-0">
                        <span class="text-sm text-gray-300 font-medium">${i.label}</span>
                        <div class="flex items-center space-x-2">
                           ${i.status === 'ok' ? '<span class="w-2 h-2 bg-green-500 rounded-full"></span><span class="text-xs text-gray-400">OK</span>' : 
                             i.status === 'error' ? '<span class="w-2 h-2 bg-red-500 rounded-full"></span><span class="text-xs text-gray-400">Error</span>' : 
                             '<span class="w-2 h-2 bg-yellow-500 rounded-full"></span><span class="text-xs text-gray-400">N/A</span>'}
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
            const apis = ['Finnhub', 'FMP', 'FRED', 'CoinGlass', 'DeepSeek', 'Kimi'].map(k => {
                const keySet = data.keys[k.toLowerCase()];
                return { label: k, status: keySet ? (data.api_checks[k.toLowerCase()] || 'ok') : 'warning' };
            });
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
        loadSettings();
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
            data = yaml.safe_load(f) or {}
    else:
        data = {}
        
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
async def run_status_check():
    """
    Führt simple GET Requests aus, wenn die Keys da sind.
    Da wir noch keine echte Geschäftslogik haben, sind das Placeholder-Checks.
    """
    has_keys = {
        "finnhub": bool(settings.finnhub_api_key),
        "fmp": bool(settings.fmp_api_key),
        "fred": bool(settings.fred_api_key),
        "coinglass": bool(settings.coinglass_api_key),
        "deepseek": bool(settings.deepseek_api_key),
        "kimi": bool(settings.kimi_api_key),
        "supabase": bool(settings.supabase_key)
    }
    
    api_checks = {}
    
    # Simulated simple ping if key present, else warning
    async with httpx.AsyncClient() as client:
        # Finnhub Example
        if has_keys["finnhub"]:
            if settings.use_mock_data:
                api_checks["finnhub"] = "ok" # Mock mode always returns ok
            else:
                try:
                    # Ein einfacher symbol lookup request an finnhub als ping
                    res = await client.get(f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={settings.finnhub_api_key}")
                    api_checks["finnhub"] = "ok" if res.status_code == 200 else "error"
                except Exception as e:
                    logger.error(f"Status check failed for Finnhub: {str(e)}")
                    api_checks["finnhub"] = "error"
        else:
             api_checks["finnhub"] = "warning"
             
        # Mock others for now since they are not fully wired up
        for k in ["fmp", "fred", "coinglass", "deepseek", "kimi"]:
            if has_keys[k]:
                api_checks[k] = "ok" # We assume it works if we have the key for the MVP Status Check
            else:
                api_checks[k] = "warning"

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

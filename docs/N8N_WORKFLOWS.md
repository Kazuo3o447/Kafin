# N8N Workflows - Automatisierungs-System für Kafin

*Erstellt: 24. März 2026*
*Zweck: Dokumentation für Agenten und Entwickler*
*Status: Produktiv - 9 aktive Workflows*

---

## 🎯 **Was sind N8N Workflows?**

N8N ist eine **Automatisierungs-Plattform** die bei Kafin als **Scheduler** für wiederkehrende Aufgaben dient. Die Workflows rufen periodisch Backend-APIs auf, um Daten zu sammeln, Reports zu generieren und das System am Laufen zu halten.

**Wichtig**: N8N ist **nur der Scheduler** - die eigentliche Business-Logic läuft im Kafin Backend!

---

## 📋 **Alle 9 Workflows im Detail**

### **1. News-Pipeline Werktags** 
```
Name: "Kafin: News-Pipeline Werktags (30min)"
Zeit: Mo-Fr 13:00-22:30 CET alle 30min
API: POST /api/news/scan
```
**Zweck**: Sammelt werktags aktuelle Nachrichten für alle Watchlist-Ticker.
- **Datenquellen**: Finnhub Company News, Google News
- **Verarbeitung**: FinBERT Sentiment-Analyse, Material-Event-Detection
- **Storage**: News-Einträge in `short_term_memory` Tabelle
- **Coverage**: Alle Ticker auf der Watchlist

---

### **2. News-Pipeline Wochenende**
```
Name: "Kafin: News-Pipeline Wochenende (Google News)"
Zeit: Sa-So 10/14/18/22 CET (alle 4h)
API: POST /api/news/scan-weekend
```
**Zweck**: Wochenend-News Coverage (nur Google News, da Finnhub begrenzt).
- **Datenquellen**: Google News API
- **Fokus**: Überbrückung der Lücke zwischen Handelswochen
- **Effizienz**: Reduzierte Frequenz am Wochenende

---

### **3. SEC-Scanner**
```
Name: "Kafin: SEC-Scanner (10min)"
Zeit: Jeden Tag alle 10 Minuten
API: POST /api/news/sec-scan
```
**Zweck**: Überwacht SEC-Filings (Form 8-K, 4) für Insider-Transaktionen.
- **Datenquellen**: SEC EDGAR API
- **Relevanz**: Insider-Aktivitäten, Material Events
- **Storage**: SEC-Daten in `short_term_memory`
- **Priorität**: Hoch - Insider-Info ist wichtig für Trading

---

### **4. Morning Briefing**
```
Name: "Kafin: Morning Briefing (Mo-Fr 08:00)"
Zeit: Mo-Fr 08:00 CET (vor Markteröffnung)
API: POST /api/reports/generate-morning
```
**Zweck**: Tägliche Marktanalyse vor Handelsbeginn.
- **Inhalt**: Marktüberblick, Watchlist-Status, Earnings-Kalender
- **Daten**: Fundamentals, Technicals, Macro, Sentiment
- **Distribution**: Dashboard, optional Telegram
- **Timing**: Strategisch vor 09:30 US Market Open

---

### **5. Post-Earnings Review**
```
Name: "Kafin: Post-Earnings Review (täglich 22:00)"
Zeit: Mo-Fr 22:00 CET (nach US-Markt-Schluss)
API: POST /api/reports/scan-earnings-results
```
**Zweck**: Scannt nach Earnings-Ergebnissen und generiert Reviews.
- **Trigger**: Überprüft ob Ticker Earnings gemeldet haben
- **Analyse**: Actual vs. Expected, Reaktion, Lessons Learned
- **Storage**: `earnings_reviews`, `long_term_memory`
- **Lernprozess**: Wichtig für zukünftige Earnings-Handel

---

### **6. Sentiment Monitor**
```
Name: "Kafin: Sentiment Monitor (stündlich)"
Zeit: Mo-Fr stündlich (09:00-17:00 CET)
API: POST /api/web-intelligence/sentiment-check
```
**Zweck**: Überwacht Sentiment-Divergenzen zwischen Quellen.
- **Vergleich**: FinBERT vs. Web Intelligence vs. Social Sentiment
- **Alerts**: Bei starken Divergenzen → Trading-Signale
- **Cooldown**: Verhindert Spam-Alerts
- **Value**: Early Warning für Sentiment-Changes

---

### **7. Peer Earnings Check**
```
Name: "Kafin: Peer Earnings Check (08:00 + 15:00)"
Zeit: Mo-Fr 08:00 + 15:00 CET
API: POST /api/web-intelligence/peer-check
```
**Zweck**: Überwacht Earnings von Peer-Unternehmen.
- **Trigger**: Wenn Peers in der gleichen Branche Earnings melden
- **Impact**: Sektor-weite Reaktionen auf eigene Ticker
- **Timing**: Vor Markteröffnung + Mid-Day Updates
- **Strategie**: Sector Rotation Plays

---

### **8. Nightly DB Backup**
```
Name: "Kafin: Nightly DB Backup (täglich 03:00)"
Zeit: Täglich 03:00 CET (nachts)
API: POST /api/admin/backup-database
```
**Zweck**: Automatisches PostgreSQL Backup.
- **Scope**: Komplette Datenbank (alle Tabellen)
- **Storage**: Docker Volume `/backups`
- **Retention**: Konfigurierbar (default 7 Tage)
- **Safety**: Disaster Recovery für Datenverlust

---

### **9. Earnings Auto-Trigger**
```
Name: "Kafin: Earnings Auto-Trigger (täglich 08:10)"
Zeit: Mo-Fr 08:10 CET (10 Min nach Morning Briefing)
API: POST /api/reports/trigger-earnings-audits
```
**Zweck**: Automatische Audit-Generierung bei starken Earnings-Signalen.
- **Trigger**: Wenn Opportunity/Torpedo-Score Schwellen erreicht
- **Aktion**: Generiert vollständigen Audit-Report
- **Decision**: Vorbereitung für manuelle Trade-Entscheidung
- **Learning**: Füttert die Decision-Snapshots für Kalibrierung

---

## ⚙️ **Technische Details**

### **Workflow-Architektur**
```
Trigger (Schedule) → HTTP Request → Backend API → Processing → Storage/Alert
```

### **Authentication**
- **Basic Auth**: `admin@example.com:changeme` (default)
- **API Key**: N8N API Key für Workflow-Management
- **Docker-Intern**: `http://n8n:5678` (Container-to-Container)
- **Extern**: `http://localhost:5678` (Browser Access)

### **Error Handling**
- **Timeouts**: 30-300s je nach Komplexität
- **Retries**: Built-in N8N Retry Logic
- **Logging**: Backend Logger + N8N Execution Logs
- **Health Checks**: `/api/n8n/status` Endpoint

### **Deployment**
```bash
# Workflows manuell erstellen/deployen
docker exec kafin-backend python -c "import asyncio; from backend.app.n8n_setup import setup_workflows; asyncio.run(setup_workflows())"

# N8N Dashboard
http://localhost:5678
```

---

## 🔄 **Workflow-Zusammenhänge**

### **Tagesablauf (Mo-Fr)**
```
03:00 - DB Backup
08:00 - Morning Briefing
08:10 - Earnings Auto-Trigger
08:00 + 15:00 - Peer Earnings Check
09:00-17:00 - Stündlich Sentiment Monitor
13:00-22:30 - News Pipeline (alle 30min)
22:00 - Post-Earnings Review
22:15 - After-Market Briefing
```

### **Datenfluss**
```
News Sources → News Pipeline → Memory Tables
Earnings Data → Post-Earnings Review → Learning
Sentiment Data → Sentiment Monitor → Alerts
Market Data → Morning Briefing → Dashboard
```

---

## 🚨 **Troubleshooting für Agenten**

### **Workflow läuft nicht?**
1. **N8N Status prüfen**: `http://localhost:5678`
2. **Backend Health**: `http://localhost:8002/health`
3. **Workflow aktiv**: Im N8N Dashboard den "Active" Schalter prüfen
4. **API Key**: N8N API Key korrekt konfiguriert?
5. **Logs**: Backend Logs + N8N Execution Logs

### **Keine Daten im Dashboard?**
1. **News Pipeline**: Läuft die News-Sammlung? `GET /api/news/memory/{ticker}`
2. **API Keys**: Sind alle Keys konfiguriert?
3. **Watchlist**: Gibt es Ticker auf der Watchlist?
4. **Cache**: Ggf. Cache invalidieren

### **Timeouts?**
1. **API Limits**: Tägliche Limits nicht überschritten
2. **Performance**: Backend unter Last? `GET /api/diagnostics/full`
3. **Network**: Externe APIs erreichbar?

### **Authentifizierungsprobleme?**
1. **N8N API Key**: In N8N Settings unter "API" generieren
2. **Environment**: `N8N_API_KEY` im Backend setzen
3. **Basic Auth**: `admin@example.com:changeme` für Browser-Zugriff

### **Manuelle Trigger**
```bash
# News manuell scannen
POST /api/news/scan

# Morning Briefing manuell
POST /api/reports/generate-morning

# Earnings Review manuell
POST /api/reports/scan-earnings-results

# N8N Setup manuell
POST /api/n8n/setup
```

---

## 📊 **Monitoring & Health**

### **Health Endpoints**
- **N8N Status**: `GET /api/n8n/status`
- **System Health**: `GET /api/diagnostics/full`
- **API Usage**: `GET /api/data/api-usage`

### **Wichtige Logs**
- **News Pipeline**: "News-Scan completed"
- **Earnings**: "Earnings results found"
- **Sentiment**: "Sentiment divergence detected"
- **Backup**: "Backup OK" / "Backup FEHLER"
- **N8N**: "n8n Workflow erstellt/fehlerhaft"

---

## 🎯 **Fazit für Agenten**

Die N8N Workflows sind das **Automatisierungs-Herz** von Kafin:

1. **Data Collection**: Kontinuierliche News- und Marktdatensammlung
2. **Analysis**: Regelmäßige Sentiment- und Earnings-Analysen  
3. **Reporting**: Tägliche Briefings und Reviews
4. **Safety**: Automatische Backups und Health Checks

**Wichtig**: Die Workflows sind **Scheduler** - die eigentliche Intelligenz und Business-Logic läuft immer im Kafin Backend! N8N sorgt nur für die zeitliche Steuerung.

### **Cheat Sheet für Agenten**
```bash
# N8N Dashboard öffnen
http://localhost:5678

# Workflow Status prüfen
GET /api/n8n/status

# Workflows neu deployen
POST /api/n8n/setup

# Manuelle Trigger (zum Testen)
POST /api/news/scan
POST /api/reports/generate-morning
POST /api/reports/scan-earnings-results
```

Wenn ein Workflow nicht funktioniert, immer zuerst das Backend prüfen - N8N ist nur der Trigger, nicht die Logik!

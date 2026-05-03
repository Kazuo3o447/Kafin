# 📋 Kafin System - Quick Reference

## 🚢 **Docker Container Ports**

| Container | Host Port | Zweck | Status |
|-----------|-----------|-------|--------|
| **kafin-frontend** | **3000** | Web Frontend | ❌ VERMEIDEN |
| **kafin-backend** | **8002** | API Backend | ❌ VERMEIDEN |
| **kafin-postgres** | **5432** | Datenbank | ❌ VERMEIDEN |
| **kafin-redis** | **6379** | Cache | ❌ VERMEIDEN |
| **kafin-n8n** | **5678** | Workflows | ❌ VERMEIDEN |

### **✅ SICHERE PORTS FÜR NEUE CONTAINER:**
- **8080-8099** - Web-Services
- **9000-9099** - APIs/Microservices  
- **5000-5099** - Development-Tools
- **4000-4099** - Monitoring/Admin

---

## 🔧 **API Endpoints**

### **Backend URL:** `http://localhost:8002`

### **Wichtige Endpoints:**
- `GET /api/data/research/{ticker}` - Research Dashboard
- `GET /api/reports/generate/{ticker}` - Audit Report
- `GET /api/watchlist` - Watchlist
- `GET /api/market/overview` - Marktübersicht

---

## 📊 **Datenstrategie**

### **Primär: yfinance** ✅
- Fundamentaldaten
- Analyst Estimates
- Key Metrics
- Earnings History

### **Fallback: FMP** ⚠️
- Nur bei yfinance-Ausfällen
- API teilweise gesperrt (403)

### **Spezialisiert:**
- **Alpaca** - Preisdaten, technische Analyse
- **Finnhub** - News, Short Interest, Insider
- **FRED** - Makrodaten

---

## 🛠️ **Wichtige Befehle**

### **Docker:**
```bash
docker compose up -d          # Starten
docker compose down            # Stoppen
docker compose restart kafin-backend  # Backend neustarten
docker ps                     # Status
```

### **Logs:**
```bash
docker logs kafin-backend --tail 100
Get-Content logs\kafin.log -Tail 50
```

### **API Test:**
```bash
Invoke-RestMethod -Uri "http://localhost:8002/api/data/research/MSFT"
```

---

## 📁 **Wichtige Dateien**

- `docker-compose.yml` - Container Konfiguration
- `backend/app/routers/data.py` - API Endpoints
- `backend/app/data/yfinance_data.py` - yfinance Funktionen
- `docs/DATA_STRATEGY.md` - Datenstrategie
- `docs/DOCKER_PORTS.md` - Port Übersicht

---

**📅 Aktualisiert:** 2026-03-25  
**🔍 System:** Kafin v7.9.4+

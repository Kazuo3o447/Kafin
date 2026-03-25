# 🚢 Docker Container Ports

## **📋 Aktive Container & Ports**

| Container | Service | Host Port | Container Port | Zweck |
|-----------|---------|-----------|----------------|-------|
| **kafin-frontend** | Next.js | **3000** | 3000 | Web Frontend |
| **kafin-backend** | FastAPI | **8002** | 8000 | API Backend |
| **kafin-postgres** | PostgreSQL | **5432** | 5432 | Datenbank |
| **kafin-redis** | Redis | **6379** | 6379 | Cache |
| **kafin-n8n** | n8n | **5678** | 5678 | Workflows |

## **⚠️ WICHTIG: Diese Ports NICHT für neue Container verwenden!**

### **Belegte Ports - VERMEIDEN:**
- ❌ **3000** - Frontend (Next.js)
- ❌ **8002** - Backend (FastAPI)  
- ❌ **5432** - PostgreSQL
- ❌ **6379** - Redis
- ❌ **5678** - n8n

## **🆗 Sichere Port-Bereiche für neue Container**

### **Empfohlene Port-Bereiche:**
- ✅ **8080-8099** - Web-Services
- ✅ **9000-9099** - APIs/Microservices  
- ✅ **5000-5099** - Development-Tools
- ✅ **4000-4099** - Monitoring/Admin

### **🎯 Beste Wahl für neue Container:**
- **8080** - Perfekt für neuen Web-Service
- **9000** - Perfekt für neue API
- **5000** - Perfekt für Development-Tool
- **4000** - Perfekt für Monitoring-Tool

## **🔧 Beispiel für neuen Container**

```yaml
# docker-compose.yml
neuer-service:
  image: dein-image
  container_name: kafin-neuer-service
  ports:
    - "8080:8080"  # ✅ Sichere Wahl!
  networks:
    - kafin-net
```

## **📝 Befehle**

### **Container Status prüfen:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

### **Port-Konflikte prüfen:**
```bash
netstat -ano | findstr ":3000\|:8002\|:5432\|:6379\|:5678"
```

---

**📅 Letzte Aktualisierung:** 2026-03-25  
**📍 Quelle:** `docker-compose.yml`  
**🔍 Zweck:** Port-Konflikte bei neuen Containern vermeiden

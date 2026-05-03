# Mock Data Policy - VERBOTEN

## 🚫 **STRIKTES VERBOT VON MOCK-DATEN**

### Grundsatz
**Kafin ist eine Live-Trading-Plattform. Mock-Daten gefährden Trading-Entscheidungen und sind daher strikt verboten.**

### Konfiguration
```bash
# .env Datei
USE_MOCK_DATA=false  # ZWINGEND - Niemals auf true setzen
```

### Auswirkungen von Mock-Daten
- **Falsche Signale**: Mock-Daten erfinden Kurse, News, Sentiments
- **Vertrauensverlust**: Trading-Entscheidungen basieren auf erfundenen Daten
- **Risiko**: Echtgeld-Verluste durch falsche Marktdaten
- **Rechtlich**: Haftung für Verluste durch falsche Daten

### Erlaubte Datenquellen
- **Live APIs**: Finnhub, FMP, FRED, yfinance, etc.
- **Echte Marktdaten**: Real-time Kurse, echte News
- **Fehlerbehandlung**: Klare Fehlermeldungen bei API-Ausfällen
- **Graceful Degradation**: Features deaktivieren statt Fake-Daten

### Verbotene Praktiken
- ❌ `USE_MOCK_DATA=true` in `.env`
- ❌ Fixture-Dateien als Produktionsdaten
- ❌ Gefälschte API-Responses
- ❌ Test-Daten in Live-Umgebung

### Erlaubte Praktiken
- ✅ `USE_MOCK_DATA=false` immer
- ✅ Klare Fehlermeldungen bei API-Problemen
- ✅ Rate Limiting und Retry-Logic
- ✅ Feature-Deaktivierung bei Daten-Ausfällen

### Fehlerbehandlung statt Mocks
```python
# FALSCH - Mock-Daten
if settings.use_mock_data:
    return load_mock_data("fake_price.json")

# RICHTIG - Echte Fehlerbehandlung
if response.status_code != 200:
    logger.error(f"API Error: {response.status_code}")
    raise APIException(f"Daten nicht verfügbar: {response.status_code}")
```

### Überwachung
- **Logs**: Alle API-Fehler werden protokolliert
- **Monitoring**: API-Ausfälle werden sofort sichtbar
- **Alerts**: Telegram-Benachrichtigung bei kritischen Ausfällen
- **Diagnostics**: `/api/diagnostics/full` zeigt API-Status

### Verantwortung
**Jeder Entwickler ist verantwortlich für:**
1. `USE_MOCK_DATA=false` sicherstellen
2. Echte Fehlerbehandlung implementieren
3. API-Keys korrekt konfigurieren
4. Datenqualität überwachen

### Konsequenzen bei Verstößen
- **Sofortige Deaktivierung** des Features
- **Rollback** zum letzten stabilen Stand
- **Dokumentation** des Vorfalls
- **Team-Kommunikation** über das Problem

---

**Trading erfordiert verlässliche Daten. Mock-Daten haben in Kafin keinen Platz.**

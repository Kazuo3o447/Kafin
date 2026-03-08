# CoinGlass API

Base-URL: `https://open-api-v3.coinglass.com/api` (V3) oder `https://open-api-v4.coinglass.com/api` (V4)
Auth: Header `CG-API-KEY: {COINGLASS_API_KEY}`
Rate-Limit: 30 Calls/Minute (Hobbyist, $29/Monat)
Docs: https://docs.coinglass.com/reference/getting-started-with-your-api
Hinweis: V4 ist aktuell empfohlen, V3 ist deprecated aber noch verfügbar

## Genutzte Endpoints

### Open Interest (aggregiert)
GET /futures/openInterest/chart?symbol=BTC&interval=1d&limit=30

Response: Array mit historischen OI-Daten
- t (int): Timestamp
- o (float): Open Interest in USD

### Funding Rate
GET /futures/funding-rates/latest

Response: Array
- symbol (str): z.B. "BTC"
- uMarginList (Array): Funding Rates pro Exchange
  - exchangeName (str)
  - rate (float): Aktuelle Funding Rate

### Liquidation Map
GET /futures/liquidation/map?symbol=BTC

Response:
- data (Object): Keys sind Preis-Levels, Values sind Arrays mit:
  - [0]: Liquidation-Preis
  - [1]: Liquidation-Volumen in USD
  - [2]: Leverage-Ratio

### Liquidation Aggregated History
GET /futures/liquidation/aggregated-history?symbol=BTC&interval=1h&limit=24

Response: Historische Liquidationsdaten
- Longs und Shorts getrennt

### Long/Short Ratio
GET /futures/longShort/chart?symbol=BTC&interval=1d&limit=7

Response: Array
- longRate (float): Long-Anteil
- shortRate (float): Short-Anteil
- longShortRatio (float): Ratio

## Interpretation für Bitcoin-Report

- Funding Rate > 0.05%: Extrem überhebelt long → Warnung
- Funding Rate < -0.03%: Überhebelt short → Warnung
- OI steigt bei seitwärts Preis: Squeeze-Aufbau
- OI-Drop > 10% plötzlich: Cascade-Liquidation

## Python-Beispiel
```python
import httpx

headers = {
    "CG-API-KEY": COINGLASS_API_KEY,
    "Content-Type": "application/json"
}
response = await client.get(
    "https://open-api-v3.coinglass.com/api/futures/funding-rates/latest",
    headers=headers
)
data = response.json()["data"]
btc_funding = [x for x in data if x["symbol"] == "BTC"][0]
```

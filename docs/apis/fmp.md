# Financial Modeling Prep (FMP) API

Base-URL: `https://financialmodelingprep.com/api/v3`
Auth: Query-Parameter `apikey={FMP_API_KEY}`
Rate-Limit: 300 Calls/Minute (Starter)
Docs: https://site.financialmodelingprep.com/developer/docs

## Konfiguration
- FMP_API_KEY: cNGraOdMmoW2sCXBhUbvzN4suozg7oWi

## Genutzte Endpoints

### Company Profile
GET /profile/{TICKER}?apikey={key}

Response: Array mit einem Element
- symbol (str): Ticker
- companyName (str): Name
- sector (str): Sektor
- industry (str): Branche
- mktCap (float): Marktkapitalisierung
- price (float): Aktueller Kurs

### Key Metrics (TTM)
GET /key-metrics-ttm/{TICKER}?apikey={key}

Response: Array mit einem Element
- peRatioTTM (float): P/E Ratio
- priceToSalesRatioTTM (float): P/S Ratio
- marketCapTTM (float): Marktkapitalisierung
- dividendYieldTTM (float): Dividendenrendite

### Analyst Estimates
GET /analyst-estimates/{TICKER}?period=quarter&limit=4&apikey={key}

Response: Array (pro Quartal ein Element)
- date (str): Datum
- estimatedRevenueAvg (float): Umsatz-Konsens
- estimatedEpsAvg (float): EPS-Konsens
- estimatedRevenueHigh/Low (float): Spannbreite
- estimatedEpsHigh/Low (float): Spannbreite
- numberAnalystEstimatedRevenue (int): Anzahl Analysten

### Earnings Surprises
GET /earnings-surprises/{TICKER}?apikey={key}

Response: Array (historische Quartale)
- date (str): Earnings-Datum
- actualEarningResult (float): Tatsächliches EPS
- estimatedEarning (float): Erwartetes EPS
Berechnung: surprise_percent = ((actual - estimated) / abs(estimated)) * 100

### Earnings Calendar
GET /earning_calendar?from={YYYY-MM-DD}&to={YYYY-MM-DD}&apikey={key}

Response: Array
- symbol (str): Ticker
- date (str): Datum
- eps (float|null): Tatsächliches EPS
- epsEstimated (float): Geschätztes EPS
- revenue (float|null): Tatsächlicher Umsatz
- revenueEstimated (float): Geschätzter Umsatz
- time (str): "bmo" oder "amc"

### S&P 500 Constituents
GET /sp500_constituent?apikey={key}

Response: Array aller S&P 500 Unternehmen
- symbol, name, sector, subSector

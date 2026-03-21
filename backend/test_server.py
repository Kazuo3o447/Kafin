"""
Simple test server for Markets Dashboard v2
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from datetime import datetime
import random

app = FastAPI(title="Kafin Test API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/data/market-overview")
async def get_market_overview():
    """Mock market overview data"""
    return {
        "timestamp": datetime.now().isoformat(),
        "indices": {
            "SPY": {"name": "S&P 500", "price": 450.25, "change_1d_pct": 1.2, "change_1m_pct": 3.5, "rsi_14": 65, "trend": "bullish", "above_sma50": True, "above_sma200": True},
            "QQQ": {"name": "NASDAQ 100", "price": 380.50, "change_1d_pct": 1.8, "change_1m_pct": 4.2, "rsi_14": 70, "trend": "bullish", "above_sma50": True, "above_sma200": True},
            "DIA": {"name": "Dow Jones", "price": 350.75, "change_1d_pct": 0.8, "change_1m_pct": 2.1, "rsi_14": 55, "trend": "neutral", "above_sma50": True, "above_sma200": False},
            "IWM": {"name": "Russell 2000", "price": 200.30, "change_1d_pct": -0.5, "change_1m_pct": 1.8, "rsi_14": 45, "trend": "bearish", "above_sma50": False, "above_sma200": True},
            "^GDAXI": {"name": "DAX", "price": 16500.00, "change_1d_pct": 0.3, "change_1m_pct": 2.5, "rsi_14": 60, "trend": "neutral", "above_sma50": True, "above_sma200": True},
            "^STOXX50E": {"name": "Euro Stoxx 50", "price": 4200.50, "change_1d_pct": 0.7, "change_1m_pct": 1.9, "rsi_14": 58, "trend": "neutral", "above_sma50": True, "above_sma200": False},
            "^N225": {"name": "Nikkei 225", "price": 28500.00, "change_1d_pct": -0.2, "change_1m_pct": 3.1, "rsi_14": 52, "trend": "neutral", "above_sma50": True, "above_sma200": True},
            "URTH": {"name": "MSCI World", "price": 95.40, "change_1d_pct": 0.9, "change_1m_pct": 2.8, "rsi_14": 62, "trend": "bullish", "above_sma50": True, "above_sma200": True},
        },
        "sector_ranking_5d": [
            {"symbol": "XLK", "name": "Technology", "perf_5d": 3.2},
            {"symbol": "XLF", "name": "Financials", "perf_5d": 2.1},
            {"symbol": "XLI", "name": "Industrial", "perf_5d": 1.8},
            {"symbol": "XLV", "name": "Health Care", "perf_5d": 1.5},
            {"symbol": "XLE", "name": "Energy", "perf_5d": 1.2},
            {"symbol": "XLP", "name": "Consumer Staples", "perf_5d": 0.8},
            {"symbol": "XLU", "name": "Utilities", "perf_5d": 0.5},
            {"symbol": "XLB", "name": "Materials", "perf_5d": 0.3},
            {"symbol": "XLRE", "name": "Real Estate", "perf_5d": -0.2},
            {"symbol": "XLY", "name": "Consumer Discretionary", "perf_5d": -0.5},
            {"symbol": "XLC", "name": "Communication", "perf_5d": -1.1},
        ],
        "macro": {
            "^VIX": {"name": "VIX", "price": 18.5, "change_1d_pct": -5.2, "rsi_14": 35},
            "TLT": {"name": "20Y+ Treasuries", "price": 95.2, "change_1d_pct": -0.8, "rsi_14": 42},
            "UUP": {"name": "US-Dollar", "price": 102.3, "change_1d_pct": 0.3, "rsi_14": 55},
            "GLD": {"name": "Gold", "price": 1850.0, "change_1d_pct": 0.5, "rsi_14": 48},
            "USO": {"name": "Öl (WTI)", "price": 78.5, "change_1d_pct": 1.2, "rsi_14": 58},
        }
    }

@app.get("/api/data/market-breadth")
async def get_market_breadth():
    """Mock market breadth data"""
    return {
        "pct_above_sma50": 65.2,
        "pct_above_sma200": 58.7,
        "breadth_signal": "stark",
        "advancing": 28,
        "declining": 12,
        "sample_size": 50,
        "breadth_index": "SP500_TOP50",
        "pct_above_sma50_5d_ago": 62.1,
        "pct_above_sma50_20d_ago": 55.3,
    }

@app.get("/api/data/macro")
async def get_macro():
    """Mock macro data"""
    return {
        "regime": "risk_on",
        "fed_rate": 5.25,
        "vix": 18.5,
        "credit_spread_bps": 320,
        "yield_curve_10y_2y": 0.35,
        "yield_curve": "normal",
        "dxy": 102.3,
    }

@app.get("/api/data/intermarket")
async def get_intermarket():
    """Mock intermarket data"""
    return {
        "assets": {
            "GLD": {"name": "Gold", "price": 1850.0, "change_1d": 0.5, "change_1w": 1.2, "change_1m": 3.8, "above_sma20": True, "trend_1m": "bullish"},
            "USO": {"name": "Öl (WTI)", "price": 78.5, "change_1d": 1.2, "change_1w": 2.1, "change_1m": 5.2, "above_sma20": True, "trend_1m": "bullish"},
            "UUP": {"name": "US-Dollar", "price": 102.3, "change_1d": 0.3, "change_1w": 0.8, "change_1m": 1.5, "above_sma20": True, "trend_1m": "neutral"},
            "TLT": {"name": "20Y+ Treasuries", "price": 95.2, "change_1d": -0.8, "change_1w": -1.2, "change_1m": -2.5, "above_sma20": False, "trend_1m": "bearish"},
            "EEM": {"name": "Emerging Markets", "price": 42.8, "change_1d": 1.5, "change_1w": 2.8, "change_1m": 4.2, "above_sma20": True, "trend_1m": "bullish"},
            "HYG": {"name": "High Yield Bonds", "price": 78.5, "change_1d": 0.2, "change_1w": 0.5, "change_1m": 1.8, "above_sma20": True, "trend_1m": "neutral"},
        },
        "signals": {
            "risk_appetite": "risk_on",
            "vix_structure": "contango",
            "credit_signal": "gesund",
        }
    }

@app.get("/api/data/market-news-sentiment")
async def get_market_news_sentiment():
    """Mock news sentiment data"""
    headlines = [
        {"headline": "Fed Signals Potential Rate Cut in Coming Months", "category": "economy", "source": "Reuters", "timestamp": 1710964800, "url": "https://reuters.com/article1", "sentiment_score": 0.25},
        {"headline": "Tech Stocks Rally on AI Optimism", "category": "technology", "source": "Bloomberg", "timestamp": 1710961200, "url": "https://bloomberg.com/article2", "sentiment_score": 0.35},
        {"headline": "Oil Prices Surge Amid Supply Concerns", "category": "energy", "source": "WSJ", "timestamp": 1710957600, "url": "https://wsj.com/article3", "sentiment_score": -0.15},
        {"headline": "Inflation Data Shows Cooling Trend", "category": "economy", "source": "CNBC", "timestamp": 1710954000, "url": "https://cnbc.com/article4", "sentiment_score": 0.18},
        {"headline": "Banking Sector Faces Regulatory Scrutiny", "category": "finance", "source": "FT", "timestamp": 1710950400, "url": "https://ft.com/article5", "sentiment_score": -0.22},
    ]
    
    return {
        "headlines": headlines,
        "category_sentiment": {
            "economy": {"score": 0.21, "count": 2, "label": "Bullish"},
            "technology": {"score": 0.35, "count": 1, "label": "Bullish"},
            "energy": {"score": -0.15, "count": 1, "label": "Bearish"},
            "finance": {"score": -0.22, "count": 1, "label": "Bearish"},
        },
        "total_analyzed": 5,
        "fetched_at": datetime.now().isoformat(),
    }

@app.get("/api/data/economic-calendar")
async def get_economic_calendar():
    """Mock economic calendar data"""
    return {
        "events": [
            {"title": "Fed Interest Rate Decision", "date": "2026-03-22T14:00:00Z", "impact": "high", "country": "US", "estimate": "5.25%", "actual": None},
            {"title": "Consumer Price Index", "date": "2026-03-23T08:30:00Z", "impact": "high", "country": "US", "estimate": "3.2%", "actual": None},
            {"title": "ECB Monetary Policy Meeting", "date": "2026-03-24T12:45:00Z", "impact": "high", "country": "EU", "estimate": "4.0%", "actual": None},
            {"title": "GDP Growth Rate", "date": "2026-03-25T10:00:00Z", "impact": "medium", "country": "US", "estimate": "2.5%", "actual": None},
            {"title": "Unemployment Rate", "date": "2026-03-26T06:00:00Z", "impact": "medium", "country": "US", "estimate": "3.8%", "actual": None},
        ]
    }

@app.post("/api/data/market-audit")
async def generate_market_audit():
    """Mock market audit"""
    return {
        "status": "success",
        "report": """**Markt-Regime Analyse (21.03.2026)**

**Aktuelles Regime:** RISK-ON mit starker Tendenz
- VIX unter 20 zeigt niedrige Volatilität
- Credit Spreads eng (320bp) -> Risikobereitschaft hoch
- Yield Curve positiv (35bp) -> keine Rezessionsgefahr
- Marktbreite stark (65% über SMA50)

**Key Signale:**
- Technology Sector führt (+3.2% 5d)
- Financials stabil (+2.1% 5d)
- Commodities (Gold, Öl) im Aufwärtstrend
- USD stabil

**Strategie-Empfehlung:**
- Long-Bias bei Tech-Qualitätsaktien (QQQ)
- Rotation in zyklische Sektoren (XLI, XLF)
- Defensive Positionierung in Utilities reduzieren
- Stop-Loss bei VIX > 25 oder Credit Spread > 500bp

**Risiko-Level:** MODERAT
**Horizont:** 2-4 Wochen""",
        "generated_at": datetime.now().isoformat(),
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

"""
ticker_resolver — Findet den besten Ticker für Datenverfügbarkeit.

Strategie:
1. Probiere den eingegebenen Ticker (z.B. VLKPF)
2. Wenn Preis fehlt: probiere bekannte Börsensuffixe
   (.DE, .F, .L, .PA, .AS, .MI, .SW, .TO, .AX)
3. Gib den Ticker zurück der einen validen Preis liefert
4. Gibt auch eine data_quality Einschätzung zurück
"""
import asyncio
from typing import Optional
import yfinance as yf
from backend.app.logger import get_logger

logger = get_logger(__name__)

# Bekannte Suffix-Kandidaten für internationale Ticker
EXCHANGE_SUFFIXES = [
    ".DE",   # Xetra (Deutschland)
    ".F",    # Frankfurt
    ".L",    # London
    ".PA",   # Paris (Euronext)
    ".AS",   # Amsterdam
    ".MI",   # Mailand
    ".SW",   # Schweiz
    ".TO",   # Toronto
    ".AX",   # Australien
    ".HK",   # Hongkong
    ".T",    # Tokyo
]

# Bekannte OTC→Primär-Mappings (manuell gepflegt)
KNOWN_MAPPINGS = {
    "VLKPF": "VOW3.DE",
    "VLKAF": "VOW3.DE",
    "BMWYY": "BMW.DE",
    "BAMXF": "BMW.DE",
    "DDAIF": "MBG.DE",
    "MBGYY": "MBG.DE",
    "SIEGY": "SIE.DE",
    "SMSSD": "SIE.DE",
    "BAYRY": "BAYN.DE",
    "RHHBY": "ROG.SW",
    "NSRGY": "NESN.SW",
    "LVMHF": "MC.PA",
    "ALIZY": "ALV.DE",
    "AZSEY": "AZM.MI",
    "ASAZY": "AMS.SW",
    "SMNEY": "SREN.SW",
    "SHLWF": "SHEL.L",
    "RYDAF": "RDS.L",
    "TTNDY": "TTM.L",
    "TOYOF": "7203.T",
    "HNDAF": "7267.T",
    "NSANY": "7201.T",
    "SSNLF": "005930.KS",
    "SFTBY": "9984.T",
    "TCEHY": "0700.HK",
    "BABA":  "9988.HK",  # Dual-listed
}


def _get_price_for_ticker(ticker_str: str) -> Optional[float]:
    """Synchron — prüft ob ein Ticker einen validen Preis liefert."""
    try:
        stock = yf.Ticker(ticker_str)
        fi = stock.fast_info
        price = getattr(fi, "last_price", None)
        if price and float(price) > 0:
            return float(price)
        # Fallback via history
        hist = stock.history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception:
        return None


def _count_data_fields(ticker_str: str) -> int:
    """Zählt wie viele Kernfelder für diesen Ticker verfügbar sind."""
    try:
        stock = yf.Ticker(ticker_str)
        info = stock.info
        core_fields = [
            "trailingPE", "forwardPE", "marketCap",
            "totalRevenue", "trailingEps", "beta",
            "fiftyTwoWeekHigh", "fiftyTwoWeekLow",
        ]
        return sum(1 for f in core_fields if info.get(f) is not None)
    except Exception:
        return 0


async def resolve_ticker(ticker: str) -> dict:
    """
    Findet den besten verfügbaren Ticker für Datenvollständigkeit.

    Returns:
        {
            "resolved_ticker": str,      # Bester Ticker
            "original_ticker": str,      # Eingegebener Ticker
            "was_resolved": bool,        # True wenn anderer Ticker genutzt
            "resolution_note": str,      # Erklärung für den User
            "data_quality": str,         # "good" | "partial" | "poor"
            "available_fields": int,     # Anzahl verfügbarer Kernfelder
        }
    """
    ticker = ticker.upper().strip()

    # 1. Bekanntes Mapping prüfen
    if ticker in KNOWN_MAPPINGS:
        primary = KNOWN_MAPPINGS[ticker]
        def _check_mapped():
            p = _get_price_for_ticker(primary)
            fields = _count_data_fields(primary) if p else 0
            return p, fields

        price, fields = await asyncio.to_thread(_check_mapped)
        if price:
            quality = "good" if fields >= 5 else "partial" if fields >= 2 else "poor"
            logger.info(
                f"Ticker Resolver: {ticker} → {primary} "
                f"(bekanntes Mapping, {fields} Felder, Preis ${price:.2f})"
            )
            return {
                "resolved_ticker": primary,
                "original_ticker": ticker,
                "was_resolved": ticker != primary,
                "resolution_note": (
                    f"Primärbörse: {primary} "
                    f"(bessere Datenverfügbarkeit als {ticker})"
                ),
                "data_quality": quality,
                "available_fields": fields,
            }

    # 2. Originalticker prüfen
    def _check_original():
        p = _get_price_for_ticker(ticker)
        fields = _count_data_fields(ticker) if p else 0
        return p, fields

    orig_price, orig_fields = await asyncio.to_thread(_check_original)

    # Originalticker hat gute Daten → nehmen
    if orig_price and orig_fields >= 5:
        return {
            "resolved_ticker": ticker,
            "original_ticker": ticker,
            "was_resolved": False,
            "resolution_note": "",
            "data_quality": "good",
            "available_fields": orig_fields,
        }

    # 3. Suffixe durchprobieren (nur wenn Original schwach)
    # Extrahiere Basis-Ticker ohne existierendes Suffix
    base = ticker.split(".")[0]

    candidates = []
    for suffix in EXCHANGE_SUFFIXES:
        candidate = f"{base}{suffix}"
        if candidate != ticker:
            candidates.append(candidate)

    def _check_all_candidates():
        results = []
        for c in candidates:
            p = _get_price_for_ticker(c)
            if p:
                fields = _count_data_fields(c)
                results.append((c, p, fields))
        return results

    found = await asyncio.to_thread(_check_all_candidates)

    # Besten Kandidaten nach Feldanzahl sortieren
    if found:
        found.sort(key=lambda x: x[2], reverse=True)
        best_ticker, best_price, best_fields = found[0]

        # Nur wechseln wenn deutlich besser
        if best_fields > orig_fields + 2:
            quality = (
                "good" if best_fields >= 5
                else "partial" if best_fields >= 2
                else "poor"
            )
            logger.info(
                f"Ticker Resolver: {ticker} → {best_ticker} "
                f"({best_fields} vs {orig_fields} Felder)"
            )
            return {
                "resolved_ticker": best_ticker,
                "original_ticker": ticker,
                "was_resolved": True,
                "resolution_note": (
                    f"Bessere Datenverfügbarkeit unter {best_ticker}. "
                    f"Original {ticker} hatte nur {orig_fields} Kernfelder."
                ),
                "data_quality": quality,
                "available_fields": best_fields,
            }

    # 4. Kein besserer Ticker gefunden
    quality = "good" if orig_fields >= 5 else "partial" if orig_fields >= 2 else "poor"
    return {
        "resolved_ticker": ticker,
        "original_ticker": ticker,
        "was_resolved": False,
        "resolution_note": (
            "" if orig_fields >= 5
            else f"Begrenzte Datenverfügbarkeit für {ticker}. "
                 "Versuche den primären Börsenticker (z.B. VOW3.DE für VW)."
        ),
        "data_quality": quality,
        "available_fields": orig_fields,
    }

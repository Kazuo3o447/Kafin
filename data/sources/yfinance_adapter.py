from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd


class YFinanceAdapter:
    """Small adapter for optional local data pulls.

    The import happens inside `fetch_snapshot` so tests and offline use do not require network or
    the dependency at import time.
    """

    def fetch_snapshot(self, ticker: str) -> dict[str, Any]:
        import yfinance as yf
        import pandas_ta as ta

        instrument = yf.Ticker(ticker)
        info = instrument.get_info()
        history = instrument.history(period="1y", auto_adjust=True)
        income_stmt = _normalize_statement(getattr(instrument, "income_stmt", None))
        cashflow_stmt = _normalize_statement(getattr(instrument, "cashflow", None))
        balance_sheet = _normalize_statement(getattr(instrument, "balance_sheet", None))

        latest_close = float(history["Close"].iloc[-1]) if not history.empty else None
        week_52_high = info.get("fiftyTwoWeekHigh")
        week_52_low = info.get("fiftyTwoWeekLow")
        average_volume = info.get("averageVolume")
        price = info.get("currentPrice") or latest_close
        sma_50 = float(history["Close"].tail(50).mean()) if len(history) >= 50 else None
        sma_200 = float(history["Close"].tail(200).mean()) if len(history) >= 200 else None
        
        # Extended Technical Analysis
        rsi_14 = None
        macd_line = None
        macd_signal = None
        recent_support_3m = None
        recent_resist_3m = None
        chart_history = []
        
        if len(history) >= 30:
            average_daily_dollar_volume = float((history["Close"].tail(30) * history["Volume"].tail(30)).mean())
            history.ta.rsi(length=14, append=True)
            history.ta.macd(append=True)
            try:
                rsi_14 = float(history["RSI_14"].iloc[-1]) if pd.notna(history["RSI_14"].iloc[-1]) else None
                macd_line = float(history["MACD_12_26_9"].iloc[-1]) if pd.notna(history["MACD_12_26_9"].iloc[-1]) else None
                macd_signal = float(history["MACDs_12_26_9"].iloc[-1]) if pd.notna(history["MACDs_12_26_9"].iloc[-1]) else None
            except KeyError:
                pass
            
            # Support/Resistance over last 3 months (~63 trading days)
            recent_3m = history["Close"].tail(63)
            recent_support_3m = float(recent_3m.min())
            recent_resist_3m = float(recent_3m.max())
            
            # Export last ~90 days for plotting in Frontend
            recent_90 = history.tail(90)
            for date_idx, row in recent_90.iterrows():
                chart_history.append({
                    "date": date_idx.strftime("%Y-%m-%d"),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"])
                })
        else:
            average_daily_dollar_volume = None
        bid = info.get("bid")
        ask = info.get("ask")
        bid_ask_spread_pct = None
        if bid and ask and price:
            bid_ask_spread_pct = ((float(ask) - float(bid)) / float(price)) * 100
        days_since_52w_high = None
        if not history.empty:
            high_date = history["Close"].idxmax()
            days_since_52w_high = int((history.index[-1] - high_date).days)

        revenues = _series_values(income_stmt, ["Total Revenue", "Operating Revenue"], limit=5)
        gross_profit = _series_values(income_stmt, ["Gross Profit"], limit=5)
        operating_income = _series_values(income_stmt, ["Operating Income"], limit=5)
        operating_cashflow = _series_values(cashflow_stmt, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], limit=5)
        free_cashflow = _series_values(cashflow_stmt, ["Free Cash Flow"], limit=5)
        stock_based_comp = _series_values(cashflow_stmt, ["Stock Based Compensation"], limit=5)
        share_counts = _series_values(income_stmt, ["Diluted Average Shares", "Basic Average Shares"], limit=3)
        total_debt = _latest_value(balance_sheet, ["Total Debt", "Long Term Debt And Capital Lease Obligation"])
        cash_and_equivalents = _latest_value(balance_sheet, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"])
        total_equity = _latest_value(balance_sheet, ["Stockholders Equity", "Common Stock Equity"])

        gross_margins = _ratio_list(gross_profit, revenues)
        operating_margins = _ratio_list(operating_income, revenues)
        fcf_margins = _ratio_list(free_cashflow, revenues)
        sbc_to_revenue = _ratio_list(stock_based_comp, revenues)
        sbc_to_ocf = _ratio_list(stock_based_comp, operating_cashflow)
        invested_capital = None
        if total_equity is not None or total_debt is not None:
            invested_capital = (total_equity or 0.0) + (total_debt or 0.0) - (cash_and_equivalents or 0.0)
        roic = None
        latest_operating_income = operating_income[0] if operating_income else None
        if latest_operating_income is not None and invested_capital not in (None, 0):
            roic = latest_operating_income / invested_capital

        latest_revenue = revenues[0] if revenues else None
        latest_gross_profit = gross_profit[0] if gross_profit else None

        return {
            "ticker": ticker.upper(),
            "company_name": info.get("longName", "unknown"),
            "exchange": info.get("exchange", "unknown"),
            "sector": info.get("sector", "unknown"),
            "industry": info.get("industry", "unknown"),
            "as_of": date.today().isoformat(),
            "metrics": {
                "price": price,
                "week_52_high": week_52_high,
                "average_daily_volume_30d": average_volume,
                "average_daily_dollar_volume_30d": average_daily_dollar_volume,
                "market_cap_usd": info.get("marketCap"),
                "forward_pe": info.get("forwardPE"),
                "ev_to_sales": info.get("enterpriseToRevenue"),
                "revenue_5y": latest_revenue,
                "revenue_growth_5y": _cagr(revenues),
                "gross_margin_5y": _average(gross_margins),
                "operating_margin_5y": _average(operating_margins),
                "fcf_margin_5y": _average(fcf_margins),
                "roic": roic,
                "share_count_trend_3y": _cagr(list(reversed(share_counts))) if len(share_counts) >= 2 else None,
                "sbc_to_revenue": _average(sbc_to_revenue),
                "sbc_to_ocf": _average(sbc_to_ocf),
                "ev_to_gross_profit": (float(info.get("enterpriseValue")) / latest_gross_profit) if info.get("enterpriseValue") and latest_gross_profit else None,
                "sma_50": sma_50,
                "sma_200": sma_200,
                "sma_200_trending_up": bool(latest_close and sma_200 and latest_close >= sma_200),
                "rsi_14": rsi_14,
                "macd_line": macd_line,
                "macd_signal": macd_signal,
                "recent_support_3m": recent_support_3m,
                "recent_resist_3m": recent_resist_3m,
                "week_52_low": week_52_low,
                "days_since_52w_high": days_since_52w_high,
                "bid_ask_spread_pct": bid_ask_spread_pct,
                "net_debt_to_ebitda": info.get("debtToEquity"),
                "instrument_type": info.get("quoteType", "equity").lower(),
                "chart_history": chart_history,
            },
            "sources": [{"name": "yfinance", "evidence_class": "B"}],
            "quality_errors": [],
        }


def _normalize_statement(frame: Any) -> pd.DataFrame:
    if frame is None or getattr(frame, "empty", True):
        return pd.DataFrame()
    normalized = frame.copy()
    if normalized.index.name is None and not normalized.empty:
        normalized.index = normalized.index.map(str)
    return normalized


def _series_values(frame: pd.DataFrame, labels: list[str], limit: int) -> list[float]:
    if frame.empty:
        return []
    for label in labels:
        if label in frame.index:
            series = frame.loc[label]
            return [float(value) for value in series.tolist()[:limit] if value not in (None, "") and pd.notna(value)]
    return []


def _latest_value(frame: pd.DataFrame, labels: list[str]) -> float | None:
    values = _series_values(frame, labels, limit=1)
    return values[0] if values else None


def _ratio_list(numerators: list[float], denominators: list[float]) -> list[float]:
    values = []
    for numerator, denominator in zip(numerators, denominators, strict=False):
        if denominator:
            values.append(numerator / denominator)
    return values


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _cagr(values: list[float]) -> float | None:
    usable = [value for value in values if value not in (None, 0)]
    if len(usable) < 2 or usable[-1] <= 0 or usable[0] <= 0:
        return None
    periods = len(usable) - 1
    return (usable[0] / usable[-1]) ** (1 / periods) - 1

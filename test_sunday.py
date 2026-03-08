import asyncio
import os
import sys

# Ensure backend can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.app.analysis.report_generator import generate_sunday_report
from backend.app.memory.watchlist import get_watchlist

async def main():
    print("Fetching watchlist...")
    wl = await get_watchlist()
    tickers = [item["ticker"] for item in wl]
    if not tickers:
        print("Watchlist ist leer. Nutze Fallback: AAPL, MSFT")
        tickers = ["AAPL", "MSFT"]
    
    print(f"Generating Sunday Report for {tickers}...")
    report = await generate_sunday_report(tickers)
    
    with open("sunday_report_test.md", "w", encoding="utf-8") as f:
        f.write(report)
        
    print("Report generated and saved to sunday_report_test.md")

if __name__ == "__main__":
    asyncio.run(main())

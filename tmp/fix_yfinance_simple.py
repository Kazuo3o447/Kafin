"""
Einfaches Skript zum Fixen der wichtigsten yfinance blocking calls.
Manuelle Vorgehensweise für bessere Kontrolle.
"""
import re

files_to_fix = [
    "backend/app/routers/data.py",
    "backend/app/routers/watchlist.py", 
    "backend/app/analysis/chart_analyst.py",
    "backend/app/analysis/sentiment_monitor.py",
    "backend/app/analysis/opportunity_scanner.py",
    "backend/app/analysis/signal_scanner.py",
    "backend/app/data/ticker_resolver.py"
]

for filepath in files_to_fix:
    print(f"\n=== Bearbeite {filepath} ===")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Stelle sicher, dass asyncio importiert ist
    if "import asyncio" not in content:
        content = re.sub(r'(import yfinance as yf)', r'import asyncio\n\1', content)
        print("  + asyncio import hinzugefügt")
    
    # Manuelles Pattern für einfache Fälle
    # yf.Ticker() -> to_thread
    content = re.sub(
        r'(\s+)(stock\s*=\s*yf\.Ticker\([^)]+\))',
        r'\1def _get_stock():\n\1\1return \2\n\1stock = await asyncio.to_thread(_get_stock)',
        content
    )
    
    # .history() -> to_thread
    content = re.sub(
        r'(\s+)(hist\s*=\s*stock\.history\([^)]+\))',
        r'\1def _get_hist():\n\1\1return \2\n\1hist = await asyncio.to_thread(_get_hist)',
        content
    )
    
    # .fast_info -> to_thread
    content = re.sub(
        r'(\s+)(fi\s*=\s*stock\.fast_info)',
        r'\1def _get_fast_info():\n\1\1return \2\n\1fi = await asyncio.to_thread(_get_fast_info)',
        content
    )
    
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filepath} aktualisiert")
    else:
        print(f"  ⚪ {filepath} keine Änderungen")

print("\n=== FERTIG ===")

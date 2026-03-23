"""
Manuelles Fix für yfinance blocking calls.
Einfache, sichere Pattern ohne komplexe Regex.
"""
import re

def fix_file(filepath):
    print(f"\n=== Fixe {filepath} ===")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Stelle sicher, dass asyncio importiert ist
    if "import asyncio" not in content:
        content = re.sub(r'(import yfinance as yf)', r'import asyncio\n\1', content)
        print("  + asyncio import hinzugefügt")
    
    # Pattern 1: yf.Ticker() -> to_thread (einfach)
    content = re.sub(
        r'(\s+)(stock\s*=\s*yf\.Ticker\([^)]+\))\n',
        r'\1def _get_stock():\n\1\1return yf.Ticker(ticker)\n\1stock = await asyncio.to_thread(_get_stock)\n',
        content
    )
    
    # Pattern 2: stock.history() -> to_thread (einfach)
    content = re.sub(
        r'(\s+)(hist\s*=\s*stock\.history\([^)]+\))\n',
        r'\1def _get_hist():\n\1\1return stock.history(period=f"{max(days, 2)}d")\n\1hist = await asyncio.to_thread(_get_hist)\n',
        content
    )
    
    # Pattern 3: .fast_info -> to_thread
    content = re.sub(
        r'(\s+)(fi\s*=\s*stock\.fast_info)\n',
        r'\1def _get_fast_info():\n\1\1return stock.fast_info\n\1fi = await asyncio.to_thread(_get_fast_info)\n',
        content
    )
    
    # Entferne doppelte leere Zeilen
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filepath} aktualisiert")
        return True
    else:
        print(f"  ⚪ {filepath} keine Änderungen")
        return False

# Liste der Dateien mit Syntax-Fehlern
files_with_errors = [
    "backend/app/routers/data.py",
    "backend/app/routers/watchlist.py", 
    "backend/app/analysis/chart_analyst.py",
    "backend/app/analysis/sentiment_monitor.py",
    "backend/app/analysis/opportunity_scanner.py",
    "backend/app/analysis/signal_scanner.py",
    "backend/app/data/ticker_resolver.py"
]

fixed_count = 0
for filepath in files_with_errors:
    if fix_file(filepath):
        fixed_count += 1

print(f"\n=== ZUSAMMENFASSUNG ===")
print(f"✅ {fixed_count}/{len(files_with_errors)} Dateien korrigiert")

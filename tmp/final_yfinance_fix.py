"""
Finale, sichere Fixes für yfinance blocking calls.
Verwdefinitive Pattern ohne Lambda-Expressions.
"""
import re

def final_fix(filepath):
    print(f"\n=== Fixe {filepath} ===")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # asyncio import hinzufügen
    if "import asyncio" not in content:
        content = re.sub(r'(import yfinance as yf)', r'import asyncio\n\1', content)
        print("  + asyncio import hinzugefügt")
    
    # Pattern 1: stock = yf.Ticker(ticker) -> to_thread
    content = re.sub(
        r'(\s+)(stock\s*=\s*yf\.Ticker\([^)]+\))',
        r'\1def _get_stock():\n\1\1return yf.Ticker(ticker)\n\1stock = await asyncio.to_thread(_get_stock)',
        content
    )
    
    # Pattern 2: hist = stock.history(...) -> to_thread
    content = re.sub(
        r'(\s+)(hist\s*=\s*stock\.history\([^)]+\))',
        r'\1def _get_hist():\n\1\1return stock.history(period=f"{max(days, 2)}d")\n\1hist = await asyncio.to_thread(_get_hist)',
        content
    )
    
    # Pattern 3: fi = stock.fast_info -> to_thread
    content = re.sub(
        r'(\s+)(fi\s*=\s*stock\.fast_info)',
        r'\1def _get_fast_info():\n\1\1return stock.fast_info\n\1fi = await asyncio.to_thread(_get_fast_info)',
        content
    )
    
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filepath} aktualisiert")
        return True
    else:
        print(f"  ⚪ {filepath} keine Änderungen")
        return False

# Kritische Dateien
critical_files = [
    "backend/app/routers/data.py",
    "backend/app/routers/watchlist.py", 
    "backend/app/data/ticker_resolver.py"
]

fixed_count = 0
for filepath in critical_files:
    if final_fix(filepath):
        fixed_count += 1

print(f"\n=== ZUSAMMENFASSUNG ===")
print(f"✅ {fixed_count}/{len(critical_files)} Dateien korrigiert")

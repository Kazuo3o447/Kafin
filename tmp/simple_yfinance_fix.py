"""
Minimaler Fix für yfinance blocking calls.
Nur die wichtigsten Pattern, keine komplexen Ersetzungen.
"""
import re

def simple_fix(filepath):
    print(f"\n=== Fixe {filepath} ===")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Nur asyncio import hinzufügen
    if "import asyncio" not in content:
        content = re.sub(r'(import yfinance as yf)', r'import asyncio\n\1', content)
        print("  + asyncio import hinzugefügt")
    
    # Nur yf.Ticker() calls ersetzen (einfachstes Pattern)
    content = re.sub(
        r'(\s+)(stock\s*=\s*yf\.Ticker\([^)]+\))',
        r'\1stock = await asyncio.to_thread(lambda: \2)',
        content
    )
    
    # Nur .history() calls ersetzen
    content = re.sub(
        r'(\s+)(hist\s*=\s*stock\.history\([^)]+\))',
        r'\1hist = await asyncio.to_thread(lambda: \2)',
        content
    )
    
    # Nur .fast_info calls ersetzen
    content = re.sub(
        r'(\s+)(fi\s*=\s*stock\.fast_info)',
        r'\1fi = await asyncio.to_thread(lambda: \2)',
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

# Nur die 3 wichtigsten Dateien fixen
critical_files = [
    "backend/app/routers/data.py",
    "backend/app/routers/watchlist.py", 
    "backend/app/data/ticker_resolver.py"
]

fixed_count = 0
for filepath in critical_files:
    if simple_fix(filepath):
        fixed_count += 1

print(f"\n=== ZUSAMMENFASSUNG ===")
print(f"✅ {fixed_count}/{len(critical_files)} kritische Dateien korrigiert")

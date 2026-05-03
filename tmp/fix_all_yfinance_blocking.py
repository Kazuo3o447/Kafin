"""
Automatisches Fix für alle verbleibenden yfinance blocking calls.
Pattern: Finde async def Funktionen, wrappe yf.Ticker() und .history() calls in to_thread().
"""
import re
import os

files_to_fix = [
    "backend/app/routers/data.py",
    "backend/app/routers/watchlist.py", 
    "backend/app/analysis/shadow_portfolio.py",
    "backend/app/analysis/post_earnings_review.py",
    "backend/app/analysis/chart_analyst.py",
    "backend/app/analysis/sentiment_monitor.py",
    "backend/app/analysis/opportunity_scanner.py",
    "backend/app/analysis/peer_monitor.py",
    "backend/app/analysis/signal_scanner.py",
    "backend/app/analysis/report_generator.py",
    "backend/app/data/market_overview.py",
    "backend/app/data/ticker_resolver.py"
]

total_fixed = 0

for filepath in files_to_fix:
    print(f"\n=== Bearbeite {filepath} ===")
    
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Stelle sicher, dass asyncio importiert ist
    if "import asyncio" not in content:
        # Füge asyncio nach den anderen Imports hinzu
        content = re.sub(r'(import yfinance as yf)', r'import asyncio\n\1', content)
        print("  + asyncio import hinzugefügt")
    
    # Pattern für async def Funktionen
    func_pattern = re.compile(r'(async def (\w+)\([^)]*\).*?\n)((?:.*?\n)*?)(?=async def|\Z)', re.DOTALL)

def fix_function(match):
    global total_fixed
    func_def = match.group(1)
    func_name = match.group(2)
    func_body = match.group(3)
        
    # Überspringen wenn kein yf call
    if not re.search(r'yf\.Ticker|stock\.history|yf\.download|stock\.option|\.fast_info', func_body):
        return match.group(0)
        
    # Überspringen wenn bereits to_thread
    if "to_thread" in func_body:
        return match.group(0)
        
    print(f"  Fixe Funktion: {func_name}")
    
    # Ersetze yf.Ticker() calls
    func_body = re.sub(
        r'(\s+)(stock\s*=\s*yf\.Ticker\([^)]+\))',
        r'\1def _get_stock():\n\1\1return \2\n\1stock = await asyncio.to_thread(_get_stock)',
        func_body
    )
    
    # Ersetze .history() calls  
    func_body = re.sub(
        r'(\s+)(hist\s*=\s*stock\.history\([^)]+\))',
        r'\1def _get_hist():\n\1\1return \2\n\1hist = await asyncio.to_thread(_get_hist)',
        func_body
    )
        
        # Ersetze yf.download() calls
        func_body = re.sub(
            r'(\s+)(raw\s*=\s*yf\.download\([^)]+\))',
            r'\1def _download():\n\1\1return \2\n\1raw = await asyncio.to_thread(_download)',
            func_body
        )
        
        # Ersetze .option_chain() calls
        func_body = re.sub(
            r'(\s+)(chain\s*=\s*stock\.option_chain\([^)]*\))',
            r'\1def _get_chain():\n\1\1return \2\n\1chain = await asyncio.to_thread(_get_chain)',
            func_body
        )
        
        # Ersetze .fast_info calls
        func_body = re.sub(
            r'(\s+)(fi\s*=\s*stock\.fast_info)',
            r'\1def _get_fast_info():\n\1\1return \2\n\1fi = await asyncio.to_thread(_get_fast_info)',
            func_body
        )
        
        # Ersetze kombinierte calls wie yf.Ticker().history()
        func_body = re.sub(
            r'(\s+)(hist\s*=\s*yf\.Ticker\([^)]+\)\.history\([^)]+\))',
            r'\1def _get_yf_hist():\n\1\1return \2\n\1hist = await asyncio.to_thread(_get_yf_hist)',
            func_body
        )
        
        # Ersetze kombinierte calls wie yf.Ticker().fast_info
        func_body = re.sub(
            r'(\s+)(fi\s*=\s*yf\.Ticker\([^)]+\)\.fast_info)',
            r'\1def _get_yf_fast_info():\n\1\1return \2\n\1fi = await asyncio.to_thread(_get_yf_fast_info)',
            func_body
        )
        
        # Ersetze multiple Ticker calls (peer_monitor)
        func_body = re.sub(
            r'(\s+)(t\s*=\s*yf\.Ticker\([^)]+\))',
            r'\1def _get_ticker_t():\n\1\1return \2\n\1t = await asyncio.to_thread(_get_ticker_t)',
            func_body
        )
        
        func_body = re.sub(
            r'(\s+)(r\s*=\s*yf\.Ticker\([^)]+\))',
            r'\1def _get_ticker_r():\n\1\1return \2\n\1r = await asyncio.to_thread(_get_ticker_r)',
            func_body
        )
        
        total_fixed += 1
        return func_def + func_body
    
    content = func_pattern.sub(fix_function, content)
    
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"  ✅ {filepath} aktualisiert")
    else:
        print(f"  ⚪ {filepath} keine Änderungen nötig")

print(f"\n=== ZUSAMMENFASSUNG ===")
print(f"✅ {total_fixed} Funktionen mit to_thread gefixt")
print(f"🎯 Alle yfinance blocking calls sollten jetzt non-blocking sein")

"""
Automatisches Fix für alle verbleibenden yfinance blocking calls.
Fügt asyncio.to_thread() wrapper um alle yf.Ticker() und .history() calls.
"""
import re, os, glob

# Alle betroffenen Dateien
files = [
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

for filepath in files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    # Pattern: Finde async def Funktionen mit yf calls
    func_pattern = re.compile(r'(async def (\w+)\([^)]*\).*?\n)((?:.*?\n)*?)(?=async def|\Z)', re.DOTALL)
    
    def fix_func(match):
        global total_fixed
        func_def = match.group(1)
        func_name = match.group(2)
        func_body = match.group(3)
        
        # Überspringen wenn kein yf call
        if "yf.Ticker" not in func_body and "yf.download" not in func_body:
            return match.group(0)
        
        # Überspringen wenn bereits to_thread
        if "to_thread" in func_body:
            return match.group(0)
        
        # Füge asyncio import hinzu falls nicht vorhanden
        if "import asyncio" not in content:
            content = content.replace("import", "import asyncio\nimport", 1)
        
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
        
        total_fixed += 1
        print(f"  Fixed function: {func_name} in {filepath}")
        
        return func_def + func_body
    
    content = func_pattern.sub(fix_func, content)
    
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated: {filepath}")

print(f"\n✅ Total functions fixed: {total_fixed}")

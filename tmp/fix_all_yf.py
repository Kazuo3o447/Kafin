"""
Automatisches Fix für alle yfinance blocking calls.
Pattern: async def -> cache check -> _fetch() -> to_thread
"""
import re, os

filepath = "backend/app/data/yfinance_data.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Finde alle Funktionen die noch nicht gefixt sind
func_pattern = re.compile(r'async def (\w+)\(.*?\n(.*?)(?=async def|\Z)', re.DOTALL)
funcs = func_pattern.findall(content)

fixed_count = 0
for func_name, func_body in funcs:
    if func_name in ["get_technical_setup", "get_earnings_history_yf", "get_vwap", "get_options_oi_analysis"]:
        continue  # bereits gefixt oder haben spezielles Pattern
    
    # Prüfe ob yf.Ticker oder stock.history im Body
    if "yf.Ticker" not in func_body and "stock.history" not in func_body:
        continue
    
    # Finde Cache-Check und Mock-Check
    lines = func_body.split("\n")
    cache_check_end = 0
    for i, line in enumerate(lines):
        if "cache_key" in line and "await cache_get" in lines[i+1]:
            cache_check_end = i + 3  # nach return cached
        elif line.strip().startswith("try:"):
            cache_check_end = i
            break
    
    # Extrahiere den zu wrappenden Teil
    body_to_wrap = "\n".join(lines[cache_check_end:])
    
    # Ersetze die Funktion
    new_body = "\n".join(lines[:cache_check_end])
    
    # Baue _fetch() Funktion
    indent = "    "
    fetch_func = f"\n{indent}def _fetch():\n"
    for line in body_to_wrap.split("\n"):
        fetch_func += f"{indent}{indent}{line}\n"
    
    # Füge to_thread Aufruf hinzu
    new_body += fetch_func
    new_body += f"\n{indent}result = await asyncio.to_thread(_fetch)\n"
    new_body += f"{indent}if result and hasattr(result, 'current_price') and result.current_price > 0:\n"
    new_body += f"{indent}{indent}await cache_set(cache_key, result.dict(), ttl_seconds=300)\n"
    new_body += f"{indent}return result\n"
    
    # Ersetze in content
    old_func = f"async def {func_name}(" + func_body
    new_func = f"async def {func_name}(" + new_body
    content = content.replace(old_func, new_func)
    fixed_count += 1
    print(f"Fixed: {func_name}")

# Speichern
with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\n✅ {fixed_count} Funktionen gefixt")

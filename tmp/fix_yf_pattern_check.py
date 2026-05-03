"""
Zeigt für jede betroffene Funktion: erste und letzte Zeile,
damit str_replace präzise gesetzt werden kann.
"""
import re

filepath = "backend/app/data/yfinance_data.py"
with open(filepath) as f:
    lines = f.readlines()

# Finde Funktionen mit direkten yf-Calls die kein to_thread nutzen
in_func = False
func_name = ""
func_start = 0
has_yf = False
has_to_thread = False

for i, line in enumerate(lines, 1):
    if line.startswith("async def "):
        if in_func and has_yf and not has_to_thread:
            print(f"\n{'='*50}")
            print(f"FUNKTION: {func_name} (Zeile {func_start}–{i-1})")
            print(f"  → braucht to_thread wrapper")
        func_name = re.match(r'async def (\w+)', line).group(1)
        func_start = i
        in_func = True
        has_yf = False
        has_to_thread = False
    elif in_func:
        if "yf.Ticker" in line or "stock.history" in line or "yf.download" in line:
            has_yf = True
        if "to_thread" in line:
            has_to_thread = True

# Letzte Funktion prüfen
if in_func and has_yf and not has_to_thread:
    print(f"\n{'='*50}")
    print(f"FUNKTION: {func_name} (Zeile {func_start}–{len(lines)})")
    print(f"  → braucht to_thread wrapper")

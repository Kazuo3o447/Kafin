"""
Wrapt alle async-Funktionen in yfinance_data.py die direkt
yf.Ticker() aufrufen in asyncio.to_thread().

Strategie: Für jede betroffene Funktion wird der komplette
Funktionskörper (nach Cache-Check und Mock-Check) in eine
innere _fetch() Funktion verschoben und mit to_thread aufgerufen.
"""
import ast, textwrap, sys

filepath = "backend/app/data/yfinance_data.py"
with open(filepath) as f:
    content = f.read()

# Funktionen die bereits korrekt to_thread nutzen — nicht anfassen
ALREADY_FIXED = {
    "get_earnings_history_yf",  # hat _fetch() + to_thread
    "get_vwap",                 # hat _calc() + to_thread
    "get_options_oi_analysis",  # hat _calc() + to_thread
}

# Funktion die wir prüfen
tree = ast.parse(content)
funcs = [n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef)]

needs_fix = []
for func in funcs:
    if func.name in ALREADY_FIXED:
        continue
    # Prüfe ob yf.Ticker direkt im Körper vorkommt (nicht in _fetch)
    for node in ast.walk(func):
        if isinstance(node, ast.AsyncFunctionDef) and node.name != func.name:
            continue  # verschachtelte Funktion — überspringen
        if isinstance(node, ast.Attribute):
            if (isinstance(node.value, ast.Name) and
                node.value.id in ('yf', 'stock') and
                node.attr in ('Ticker', 'history', 'download',
                              'options', 'option_chain', 'fast_info',
                              'earnings_history', 'info')):
                needs_fix.append(func.name)
                break

print(f"Funktionen die to_thread brauchen: {set(needs_fix)}")
print("\nDiese Funktionen müssen manuell oder mit str_replace gefixt werden.")
print("Nutze das Pattern aus Schritt 4b für jede Funktion.")

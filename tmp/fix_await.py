import re, os, glob

# Alle Python-Dateien im Backend
files = glob.glob("backend/app/**/*.py", recursive=True)
files = [f for f in files if "__pycache__" not in f]

# Pattern: cache_get/cache_set/cache_invalidate ohne await davor
# Ignoriere: Funktionsdefinitionen, Kommentare, bereits mit await
PATTERN = re.compile(
    r'^(\s+)(cached\s*=\s*)?(cache_get|cache_set|cache_invalidate|cache_invalidate_prefix)\(',
    re.MULTILINE
)

fixed_files = []
for filepath in files:
    with open(filepath, "r") as f:
        original = f.read()

    lines = original.split("\n")
    new_lines = []
    changed = False

    for line in lines:
        # Überspringe Kommentare und Definitionen
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("async def cache") or stripped.startswith("def cache"):
            new_lines.append(line)
            continue

        # Prüfe ob cache_get/set/invalidate ohne await
        # Erlaubte Fälle die kein await brauchen: keine
        indent = len(line) - len(line.lstrip())
        prefix = " " * indent

        # Pattern: "    cached = cache_get(" → "    cached = await cache_get("
        if re.match(r'\s+\w+\s*=\s*cache_get\(', line) and 'await' not in line:
            line = line.replace('cache_get(', 'await cache_get(', 1)
            changed = True

        # Pattern: "    cache_set(" → "    await cache_set("
        elif re.match(r'\s+cache_set\(', line) and 'await' not in line:
            line = line.replace('cache_set(', 'await cache_set(', 1)
            changed = True

        # Pattern: "    cache_invalidate(" → "    await cache_invalidate("
        elif re.match(r'\s+cache_invalidate\(', line) and 'await' not in line:
            line = line.replace('cache_invalidate(', 'await cache_invalidate(', 1)
            changed = True

        # Pattern: "    cache_invalidate_prefix(" → await
        elif re.match(r'\s+cache_invalidate_prefix\(', line) and 'await' not in line:
            line = line.replace('cache_invalidate_prefix(', 'await cache_invalidate_prefix(', 1)
            changed = True

        # Pattern: if not cache_get( → if not await cache_get(
        elif 'cache_get(' in line and 'await' not in line and 'def cache' not in line:
            line = line.replace('cache_get(', 'await cache_get(', 1)
            changed = True

        new_lines.append(line)

    if changed:
        with open(filepath, "w") as f:
            f.write("\n".join(new_lines))
        fixed_files.append(filepath)
        print(f"  Geändert: {filepath}")

print(f"\n✅ {len(fixed_files)} Dateien aktualisiert")

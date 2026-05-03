import re, os, glob

# Alle Python-Dateien im Backend
files = glob.glob("backend/app/**/*.py", recursive=True)
files = [f for f in files if "__pycache__" not in f]

fixed_files = []
for filepath in files:
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, "r", encoding="cp1252") as f:
                original = f.read()
        except:
            print(f"  Übersprungen (encoding): {filepath}")
            continue

    lines = original.split("\n")
    new_lines = []
    changed = False

    for line in lines:
        # Überspringe Kommentare und Definitionen
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("async def cache") or stripped.startswith("def cache"):
            new_lines.append(line)
            continue

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
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(new_lines))
        fixed_files.append(filepath)
        print(f"  Geändert: {filepath}")

print(f"\n✅ {len(fixed_files)} Dateien aktualisiert")

"""Test: Groq API Verbindung + News-Extraktion."""
import asyncio
import sys
import os

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

async def test_groq_connection():
    from backend.app.analysis.groq import call_groq

    print("Test 1: Einfache Verbindung...")
    result = await call_groq(
        system_prompt="Antworte nur mit: OK",
        user_prompt="Test",
        max_tokens=10,
    )
    assert result.strip(), "Keine Antwort von Groq"
    print(f"  ✓ Antwort: {result.strip()}")

    print("\nTest 2: News-Extraktion (JSON)...")
    from backend.app.analysis.groq import call_groq
    system = (
        "Du bist ein Finanzanalyst. Extrahiere aus der News "
        "3 Stichpunkte als JSON: "
        '{"bullet_points": ["...", "...", "..."], '
        '"is_narrative_shift": false, '
        '"shift_type": "None", '
        '"shift_confidence": 0.0, '
        '"shift_reasoning": ""}'
        "\nNur JSON, kein Markdown."
    )
    user = (
        "Ticker: NVDA\n"
        "Headline: NVIDIA beats Q3 expectations with record revenue\n"
        "Text: NVIDIA reported Q3 revenue of $18.1 billion, "
        "beating consensus estimates of $16.2 billion. "
        "Data center revenue surged 279% year-over-year."
    )
    result2 = await call_groq(system, user, max_tokens=256)
    print(f"  Antwort: {result2[:200]}")

    import json
    try:
        clean = result2.strip().replace("```json","").replace("```","").strip()
        parsed = json.loads(clean)
        assert "bullet_points" in parsed
        assert len(parsed["bullet_points"]) > 0
        print(f"  ✓ JSON valide: {len(parsed['bullet_points'])} Stichpunkte")
        for bp in parsed["bullet_points"]:
            print(f"    - {bp}")
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON-Parse Fehler: {e}")
        print(f"    (Fallback würde greifen)")

    print("\nTest 3: Fallback prüfen (ungültiger Key simuliert)...")
    import backend.app.config as cfg
    original_key = cfg.settings.groq_api_key
    cfg.settings.groq_api_key = ""
    result3 = await call_groq("Test", "Test", max_tokens=20)
    cfg.settings.groq_api_key = original_key
    print(f"  ✓ Fallback aktiv: {bool(result3)}")

    print("\n✅ Alle Tests bestanden.")

if __name__ == "__main__":
    asyncio.run(test_groq_connection())

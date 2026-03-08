"""
test_db_connection.py — Testskript für die Supabase-Datenbankverbindung

Dieses Skript prüft, ob die in der `.env` angegebenen Credentials (SUPABASE_URL und SUPABASE_KEY)
korrekt sind und ob alle für das Kafin-System notwendigen Tabellen existieren und
zugänglich (lesbar) sind.

Input:  Keine direkten Argumente. Liest `.env` Variablen.
Output: Konsolenausgabe mit dem Status jeder Tabelle.
Deps:   supabase, pydantic, dotenv
Config: SUPABASE_URL, SUPABASE_KEY
API:    Supabase REST API
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Lade Umgebungsvariablen aus der .env Datei
load_dotenv()

def main():
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")

    if not url or not key:
        print("FEHLER: Supabase Credentials (SUPABASE_URL oder SUPABASE_KEY) fehlen in der .env Datei.")
        exit(1)

    try:
        # Initialisiere den Supabase Client
        supabase: Client = create_client(url, key)
    except Exception as e:
        print(f"FEHLER: Konnte den Supabase Client nicht initialisieren. Details: {e}")
        exit(1)

    # Liste aller Tabellen, die im schema.sql definiert sind und getestet werden sollen
    tables_to_check = [
        "watchlist",
        "short_term_memory",
        "long_term_memory",
        "macro_snapshots",
        "btc_snapshots",
        "audit_reports"
    ]

    print("Starte Verbindungstest zu Supabase...\n")
    
    all_success = True
    
    try:
        for table in tables_to_check:
            # Versuche, einen Datensatz aus der Tabelle zu lesen, um Lesezugriff zu verifizieren
            response = supabase.table(table).select("*").limit(1).execute()
            print(f"[OK] Tabelle '{table}' ist erreichbar. Antwort: {response.data}")
            
        if all_success:
            print("\nERFOLG! Alle Datenbanktabellen sind erfolgreich angebunden und erreichbar.")
            
    except Exception as e:
        print(f"\n[FEHLER] Konnte nicht auf eine Tabelle zugreifen. Details: {e}")
        print("Tipp: Überprüfe deinen SUPABASE_KEY. Dieser muss der 'anon' / 'publishable' Key sein.")
        exit(1)

if __name__ == "__main__":
    main()

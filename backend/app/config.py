"""
config — Zentrale Konfiguration der Anwendung

Input:  Environment Variables (.env) und config/settings.yaml
Output: Settings-Objekt (Pydantic Model)
Deps:   pydantic_settings, yaml
Config: Keine
API:    Keine
"""
import os
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict

def load_yaml_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

# Optional: Laden der settings.yaml (Fallback auf leeres Dict, falls nicht vorhanden)
yaml_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "settings.yaml")
yaml_data = load_yaml_config(yaml_path) if os.path.exists(yaml_path) else {}

class Settings(BaseSettings):
    # App Settings
    app_name: str = yaml_data.get("app", {}).get("name", "Antigravity")
    environment: str = yaml_data.get("app", {}).get("env", "dev")
    use_mock_data: bool = yaml_data.get("flags", {}).get("use_mock_data", False)
    
    # API Keys (werden via .env überschrieben)
    finnhub_api_key: str = ""
    fmp_api_key: str = ""
    fred_api_key: str = ""
    coinglass_api_key: str = ""
    deepseek_api_key: str = ""
    kimi_api_key: str = ""
    
    # Supabase (via .env)
    supabase_url: str = ""
    supabase_key: str = ""

    # Telegram (via .env)
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()

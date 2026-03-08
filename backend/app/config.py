"""
config — Zentrale Konfiguration der Anwendung

Input:  Environment Variables (.env) und config/settings.yaml
Output: Settings-Objekt (Pydantic Model)
Deps:   pydantic_settings, yaml, python-dotenv
Config: Keine
API:    Keine
"""
import os
import yaml
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

def load_yaml_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

YAML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "settings.yaml")
ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env")

class Settings(BaseSettings):
    # App Settings
    app_name: str = "Kafin"
    environment: str = "development"
    use_mock_data: bool = False
    log_level: str = "INFO"
    report_language: str = "de"
    
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
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    def reload_from_yaml(self):
        """Reloads configuration dynamically from YAML"""
        yaml_data = load_yaml_config(YAML_PATH) if os.path.exists(YAML_PATH) else {}
        self.environment = yaml_data.get("environment", self.environment)
        self.use_mock_data = yaml_data.get("use_mock_data", self.use_mock_data)
        self.log_level = yaml_data.get("log_level", self.log_level)
        self.report_language = yaml_data.get("report_language", self.report_language)

    @property
    def apis(self) -> dict:
        return load_yaml_config(os.path.join(os.path.dirname(YAML_PATH), "apis.yaml"))

    @property
    def scoring(self) -> dict:
        return load_yaml_config(os.path.join(os.path.dirname(YAML_PATH), "scoring.yaml"))

    @property
    def alerts(self) -> dict:
        return load_yaml_config(os.path.join(os.path.dirname(YAML_PATH), "alerts.yaml"))

settings = Settings()
settings.reload_from_yaml()

"""Application configuration and settings management."""

import os
import json
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
SUMMARIES_DIR = DATA_DIR / "summaries"
DB_PATH = DATA_DIR / "meetingmate.db"
SETTINGS_PATH = DATA_DIR / "settings.json"
GDRIVE_CREDENTIALS_PATH = DATA_DIR / "gdrive_credentials.json"
GDRIVE_TOKEN_PATH = DATA_DIR / "gdrive_token.json"

# Ensure directories exist
for d in [DATA_DIR, UPLOADS_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class Settings(BaseSettings):
    """App settings — loaded from settings.json, editable via UI."""

    # VibeVoice-ASR (Microsoft) — 語音轉文字 + 說話者辨識 + 時間戳
    # 模型清單：https://huggingface.co/microsoft/VibeVoice-ASR
    vibevoice_model: str = "microsoft/VibeVoice-ASR"  # 7B 完整模型

    # LLM provider
    llm_provider: str = "openai"  # openai | anthropic | gemini
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-pro"

    # Google Drive — path supports nested folders with /
    gdrive_folder_name: str = "Temp/MeetingMinute"
    gdrive_auto_backup: bool = True

    class Config:
        env_file = BASE_DIR / ".env"
        extra = "ignore"


def load_settings() -> Settings:
    """Load settings from JSON file, falling back to defaults."""
    if SETTINGS_PATH.exists():
        try:
            data = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            return Settings(**data)
        except Exception:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    """Persist settings to JSON file."""
    SETTINGS_PATH.write_text(
        json.dumps(settings.model_dump(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

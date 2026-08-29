import json
from pathlib import Path
from typing import Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class Config:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_file = config_path or (PROJECT_ROOT / "config.json")
        self.data: Dict[str, Any] = self._load()
        self._ensure_directories()

    def _load(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_file}")
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def reload(self) -> None:
        self.data = self._load()

    def save(self) -> None:
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    @property
    def event_name(self) -> str:
        return self.data.get("event_name", "Conference Headshots 2026")

    @property
    def google_sheet_csv_url(self) -> str:
        return self.data.get("google_sheet_csv_url", "")

    @property
    def poll_interval_seconds(self) -> int:
        return int(self.data.get("poll_interval_seconds", 30))

    @property
    def auto_send_emails(self) -> bool:
        return bool(self.data.get("auto_send_emails", True))

    @property
    def email_rate_limit_seconds(self) -> float:
        return float(self.data.get("email_rate_limit_seconds", 1.8))

    @property
    def gmail_config(self) -> Dict[str, Any]:
        return self.data.get("gmail", {})

    @property
    def zenfolio_config(self) -> Dict[str, Any]:
        return self.data.get("zenfolio", {})

    @property
    def database_path(self) -> Path:
        rel = self.data.get("paths", {}).get("database_file", "data/booth.db")
        return PROJECT_ROOT / rel

    @property
    def tether_ingest_dir(self) -> Path:
        rel = self.data.get("paths", {}).get("tether_ingest_dir", "shoot_folders/01_Tether_Ingest")
        return PROJECT_ROOT / rel

    @property
    def ready_to_deliver_dir(self) -> Path:
        rel = self.data.get("paths", {}).get("ready_to_deliver_dir", "shoot_folders/03_Ready_To_Deliver")
        return PROJECT_ROOT / rel

    def _ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.tether_ingest_dir.mkdir(parents=True, exist_ok=True)
        self.ready_to_deliver_dir.mkdir(parents=True, exist_ok=True)

# Singleton instance
config = Config()

from dataclasses import dataclass
import json
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]


@dataclass(slots=True, frozen=True)
class Settings:
    api_id: int
    api_hash: str
    default_delay: float = 1.0


def _load() -> Settings:
    """
    Смешивает переменные из .env и settings.json.
    Приоритет: .env > settings.json.
    """
    load_dotenv(BASE_DIR / ".env")

    jcfg: dict = {}
    json_path = BASE_DIR / "settings.json"
    if json_path.exists():
        with open(json_path, encoding="utf-8") as fp:
            jcfg = json.load(fp)

    api_id = int(os.getenv("API_ID") or jcfg.get("API_ID", 28532690))
    api_hash = os.getenv("API_HASH") or jcfg.get("API_HASH", "1a2e04f22cf3ba451e06372bf1a4f022")

    if not api_id or not api_hash:
        raise RuntimeError("API_ID / API_HASH не заданы в .env или settings.json")

    return Settings(
        api_id=api_id,
        api_hash=api_hash,
        default_delay=float(jcfg.get("DEFAULT_DELAY", 1.0)),
    )


settings = _load()

def set_default_delay(delay: float) -> None:
    """
    Update DEFAULT_DELAY in settings.json.
    """
    json_path = BASE_DIR / "settings.json"
    data: dict = {}
    if json_path.exists():
        with open(json_path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
    data["DEFAULT_DELAY"] = delay
    with open(json_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=2, ensure_ascii=False)
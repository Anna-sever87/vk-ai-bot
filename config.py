import os
from dataclasses import dataclass
from pathlib import Path
from typing import FrozenSet

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Читаем настройки из файла .env (значения из .env главнее системных переменных)
load_dotenv(BASE_DIR / ".env", override=True)


@dataclass(frozen=True)
class Config:
    vk_token: str
    ai_api_key: str
    ai_base_url: str
    ai_model: str
    max_message_length: int
    max_history_messages: int
    context_messages: int
    allowed_user_ids: FrozenSet[int]
    log_level: str


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value.startswith("your_"):
        raise RuntimeError(f"Не заполнена переменная {name}. Проверь файл .env.")
    return value


def _parse_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if minimum <= value <= maximum else default


def _parse_ids(text: str) -> FrozenSet[int]:
    ids = set()
    for part in text.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            raise RuntimeError("ALLOWED_USER_IDS должен содержать числа (ID во ВКонтакте) через запятую.")
    return frozenset(ids)


def load_config() -> Config:
    return Config(
        vk_token=_require("VK_TOKEN"),
        ai_api_key=_require("AI_API_KEY"),
        ai_base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1").strip(),
        ai_model=os.getenv("AI_MODEL", "gpt-4o-mini").strip(),
        max_message_length=_parse_int("MAX_MESSAGE_LENGTH", 4000, 100, 4000),
        max_history_messages=_parse_int("MAX_HISTORY_MESSAGES", 100, 2, 1000),
        context_messages=_parse_int("CONTEXT_MESSAGES", 20, 2, 100),
        allowed_user_ids=_parse_ids(os.getenv("ALLOWED_USER_IDS", "")),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )
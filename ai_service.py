import logging
from dataclasses import dataclass
from typing import Dict, List

from openai import AsyncOpenAI

from config import Config

logger = logging.getLogger("ai_service")


class AIServiceError(Exception):
    """Не удалось получить ответ от языковой модели."""


@dataclass
class AIResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class AIService:
    """Работа с языковой моделью через API, совместимый с OpenAI (OpenAI напрямую или ProxyAPI)."""

    def __init__(self, config: Config) -> None:
        self.model = config.ai_model
        self.client = AsyncOpenAI(
            api_key=config.ai_api_key,
            base_url=config.ai_base_url,
            timeout=60.0,
            max_retries=1,
        )

    async def ask(self, messages: List[Dict[str, str]]) -> AIResult:
        """Отправляет модели список сообщений (system, история, новый вопрос) и возвращает ответ."""
        try:
            response = await self.client.chat.completions.create(model=self.model, messages=messages)
        except Exception as e:
            raise AIServiceError(f"Ошибка запроса к модели {self.model}: {e}") from e

        choices = getattr(response, "choices", None) or []
        text = ""
        if choices:
            text = (choices[0].message.content or "").strip()
        if not text:
            raise AIServiceError("Модель вернула пустой ответ.")

        usage = getattr(response, "usage", None)
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        total = int(getattr(usage, "total_tokens", 0) or 0) or prompt + completion
        return AIResult(text=text, prompt_tokens=prompt, completion_tokens=completion, total_tokens=total)
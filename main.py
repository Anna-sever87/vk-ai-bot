import logging
import sys

from ai_service import AIService
from bot import create_bot
from config import BASE_DIR, load_config
from controller import BotController
from storage import UserStorage

logger = logging.getLogger("main")


def setup_logging(level_name: str) -> None:
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(BASE_DIR / "bot.log", encoding="utf-8"),
        ],
    )


def main() -> int:
    try:
        config = load_config()
    except RuntimeError as e:
        print(f"Ошибка настроек: {e}")
        return 1
    setup_logging(config.log_level)

    storage = UserStorage(BASE_DIR / "users", config.max_history_messages)
    controller = BotController(config, storage, AIService(config))
    bot = create_bot(config, controller)

    if not config.allowed_user_ids:
        logger.warning("ALLOWED_USER_IDS не задан: боту сможет писать любой, кто найдёт сообщество")
    logger.info("Бот запущен. Модель: %s, адрес API: %s", config.ai_model, config.ai_base_url)
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.exception("Бот остановился из-за ошибки")
        print(
            f"Ошибка: {e}\n"
            "Проверьте VK_TOKEN в .env: у токена должны быть права «управление сообществом» "
            "и «сообщения сообщества». Также в настройках сообщества должен быть включён Long Poll API."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
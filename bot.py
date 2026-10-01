import logging

from vkbottle.bot import Bot, Message

from config import Config
from controller import BotController, Reply

logger = logging.getLogger("bot")


def create_bot(config: Config, controller: BotController) -> Bot:
    """Создаёт бота ВКонтакте (Long Poll) и подключает к нему логику из controller."""
    bot = Bot(token=config.vk_token)

    @bot.on.message()
    async def on_message(message: Message) -> None:
        # Беседы сообщества не обрабатываем: бот работает только в личных сообщениях
        if message.peer_id != message.from_id:
            return

        async def typing() -> None:
            await bot.api.messages.set_activity(type="typing", peer_id=message.peer_id)

        try:
            replies = await controller.handle(message.from_id, message.text, typing)
        except Exception:
            logger.exception("Необработанная ошибка у пользователя %s", message.from_id)
            replies = [Reply("Произошла ошибка. Попробуйте ещё раз.")]

        for reply in replies:
            try:
                if reply.keyboard:
                    await message.answer(reply.text, keyboard=reply.keyboard)
                else:
                    await message.answer(reply.text)
            except Exception:
                logger.exception("Не удалось отправить сообщение пользователю %s", message.from_id)
                break

    return bot
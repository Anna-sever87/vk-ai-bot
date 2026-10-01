import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

import keyboards as kb
from ai_service import AIService, AIServiceError
from config import Config
from models import ChatMessage, UserData
from modes import DEFAULT_MODE, get_mode, mode_by_title, system_prompt
from storage import UserStorage
from utils import clean_markdown, split_text

logger = logging.getLogger("controller")

MAX_DIALOGS = 10  # максимум диалогов у одного пользователя

TypingCallback = Callable[[], Awaitable[None]]

START_WORDS = {"начать", "start", "/start", "меню", "главное меню", "назад"}
ID_WORDS = {"мой id", "id", "/id"}
MODE_WORDS = {"режим", "режим общения"}

WELCOME_TEXT = (
    "Здравствуйте! Я AI-помощник. Могу вести диалог, помнить его контекст и менять стиль общения.\n\n"
    "Что я умею:\n"
    "• вести несколько независимых диалогов (у каждого своя память);\n"
    "• работать в разных режимах: помощник, программист, преподаватель, бизнес-консультант, собеседник;\n"
    "• хранить историю ваших диалогов.\n\n"
    "Просто напишите вопрос или выберите действие кнопками внизу."
)

HELP_TEXT = (
    "Как пользоваться ботом:\n"
    "• просто напишите сообщение, и я отвечу с учётом предыдущих сообщений диалога;\n"
    "• «Новый диалог» начинает отдельный разговор с чистой памятью;\n"
    "• «Мои диалоги» показывает список диалогов, чтобы вернуться к любому из них;\n"
    "• «Режим общения» меняет роль и стиль ответов (действует только в текущем диалоге);\n"
    "• «Очистить диалог» стирает историю текущего диалога;\n"
    "• «Удалить диалог» удаляет текущий диалог;\n"
    "• «Статистика» показывает число диалогов, сообщений и потраченных токенов;\n"
    "• «Мой id» показывает ваш ID во ВКонтакте."
)


@dataclass
class Reply:
    text: str
    keyboard: Optional[str] = None


class BotController:
    """Логика бота: команды, диалоги, режимы и общение с моделью. Не зависит от библиотеки VK."""

    def __init__(self, config: Config, storage: UserStorage, ai: AIService) -> None:
        self.config = config
        self.storage = storage
        self.ai = ai
        self._locks = defaultdict(asyncio.Lock)

    def _allowed(self, user_id: int) -> bool:
        return not self.config.allowed_user_ids or user_id in self.config.allowed_user_ids

    async def handle(self, user_id: int, text: str, typing: Optional[TypingCallback] = None) -> List[Reply]:
        text = (text or "").strip()
        if not text:
            return []
        command = text.casefold()

        # Свой ID можно узнать всегда: он нужен, чтобы внести его в список допущенных
        if command in ID_WORDS:
            return [Reply(f"Ваш ID во ВКонтакте: {user_id}", kb.main_menu())]
        if not self._allowed(user_id):
            logger.warning("Отказано в доступе пользователю %s", user_id)
            return [Reply("Доступ к этому боту ограничен.")]

        # Сообщения одного пользователя обрабатываются по очереди
        async with self._locks[user_id]:
            try:
                return await self._dispatch(user_id, text, command, typing)
            except Exception:
                logger.exception("Ошибка при обработке сообщения пользователя %s", user_id)
                return [Reply("Произошла ошибка. Попробуйте ещё раз.", kb.main_menu())]

    async def _dispatch(self, user_id: int, text: str, command: str,
                        typing: Optional[TypingCallback]) -> List[Reply]:
        user = self.storage.load(user_id)

        if command in START_WORDS:
            user.active_dialog(DEFAULT_MODE)
            self.storage.save(user)
            return [Reply(WELCOME_TEXT, kb.main_menu())]
        if command == kb.BTN_HELP.casefold():
            return [Reply(HELP_TEXT, kb.main_menu())]
        if command == kb.BTN_NEW_DIALOG.casefold():
            return [self._new_dialog(user)]
        if command == kb.BTN_MY_DIALOGS.casefold():
            return [self._list_dialogs(user)]
        if command.startswith(kb.BTN_OPEN_PREFIX.casefold()):
            return [self._open_dialog(user, text[len(kb.BTN_OPEN_PREFIX):])]
        if command == kb.BTN_DELETE.casefold():
            return [self._delete_dialog(user)]
        if command in MODE_WORDS:
            return [self._show_modes(user)]
        mode = mode_by_title(text)
        if mode is not None:
            return [self._set_mode(user, mode.key)]
        if command == kb.BTN_CLEAR.casefold():
            return [self._clear_dialog(user)]
        if command == kb.BTN_STATS.casefold():
            return [self._stats(user)]
        return await self._chat(user, text, typing)

    # ----- команды меню -----
    def _new_dialog(self, user: UserData) -> Reply:
        if len(user.dialogs) >= MAX_DIALOGS:
            return Reply(
                f"Достигнут лимит диалогов ({MAX_DIALOGS}). Удалите ненужный командой «{kb.BTN_DELETE}».",
                kb.dialogs_menu(sorted(user.dialogs), user.active_dialog_id),
            )
        dialog = user.create_dialog(DEFAULT_MODE)
        self.storage.save(user)
        return Reply(
            f"Создан «{dialog.title}». Режим: {get_mode(dialog.mode).title}. Память этого диалога пока пуста.",
            kb.main_menu(),
        )

    def _list_dialogs(self, user: UserData) -> Reply:
        user.active_dialog(DEFAULT_MODE)
        lines = ["Ваши диалоги:"]
        for dialog_id in sorted(user.dialogs):
            dialog = user.dialogs[dialog_id]
            active = " (активный)" if dialog_id == user.active_dialog_id else ""
            lines.append(
                f"• {dialog.title}: {get_mode(dialog.mode).title}, сообщений: {len(dialog.messages)}{active}"
            )
        lines.append("\nЧтобы переключиться, нажмите «Открыть» с номером диалога.")
        self.storage.save(user)
        return Reply("\n".join(lines), kb.dialogs_menu(sorted(user.dialogs), user.active_dialog_id))

    def _open_dialog(self, user: UserData, number: str) -> Reply:
        try:
            dialog_id = int(number.strip())
        except ValueError:
            dialog_id = -1
        dialog = user.dialogs.get(dialog_id)
        if dialog is None:
            return Reply("Такого диалога нет.", kb.dialogs_menu(sorted(user.dialogs), user.active_dialog_id))
        user.active_dialog_id = dialog_id
        self.storage.save(user)
        return Reply(
            f"Открыт «{dialog.title}». Режим: {get_mode(dialog.mode).title}. "
            f"Сообщений в истории: {len(dialog.messages)}.",
            kb.main_menu(),
        )

    def _delete_dialog(self, user: UserData) -> Reply:
        dialog = user.active_dialog(DEFAULT_MODE)
        if len(user.dialogs) <= 1:
            dialog.messages = []
            self.storage.save(user)
            return Reply("Это ваш единственный диалог, поэтому я просто очистила его историю.", kb.main_menu())
        title = dialog.title
        user.delete_dialog(dialog.id)
        current = user.dialogs[user.active_dialog_id]
        self.storage.save(user)
        return Reply(f"«{title}» удалён. Сейчас открыт «{current.title}».", kb.main_menu())

    def _show_modes(self, user: UserData) -> Reply:
        dialog = user.active_dialog(DEFAULT_MODE)
        self.storage.save(user)
        return Reply(
            f"Выберите режим общения для «{dialog.title}». Сейчас: {get_mode(dialog.mode).title}.",
            kb.modes_menu(dialog.mode),
        )

    def _set_mode(self, user: UserData, mode_key: str) -> Reply:
        dialog = user.active_dialog(DEFAULT_MODE)
        dialog.mode = mode_key
        self.storage.save(user)
        return Reply(
            f"Режим общения изменён на «{get_mode(mode_key).title}». "
            f"Он действует только в текущем диалоге («{dialog.title}»).",
            kb.main_menu(),
        )

    def _clear_dialog(self, user: UserData) -> Reply:
        dialog = user.active_dialog(DEFAULT_MODE)
        dialog.messages = []
        self.storage.save(user)
        return Reply(f"История диалога «{dialog.title}» очищена.", kb.main_menu())

    def _stats(self, user: UserData) -> Reply:
        dialog = user.active_dialog(DEFAULT_MODE)
        total_messages = sum(len(d.messages) for d in user.dialogs.values())
        self.storage.save(user)
        return Reply(
            "Ваша статистика:\n"
            f"• диалогов: {len(user.dialogs)}\n"
            f"• сообщений во всех диалогах: {total_messages}\n"
            f"• запросов к модели: {user.requests_count}\n"
            f"• потрачено токенов: {user.tokens_used}\n"
            f"• активный диалог: {dialog.title}, режим: {get_mode(dialog.mode).title}",
            kb.main_menu(),
        )

    # ----- общение с моделью -----
    async def _chat(self, user: UserData, text: str, typing: Optional[TypingCallback]) -> List[Reply]:
        if len(text) > self.config.max_message_length:
            return [Reply(
                f"Сообщение слишком длинное (максимум {self.config.max_message_length} символов).",
                kb.main_menu(),
            )]

        dialog = user.active_dialog(DEFAULT_MODE)
        # Краткосрочная память: последние сообщения активного диалога + новый вопрос
        history = dialog.messages[-self.config.context_messages:]
        messages = [{"role": "system", "content": system_prompt(dialog.mode)}]
        messages += [{"role": m.role, "content": m.content} for m in history]
        messages.append({"role": "user", "content": text})

        if typing is not None:
            try:
                await typing()
            except Exception:
                logger.debug("Не удалось отправить статус «печатает»", exc_info=True)

        try:
            result = await self.ai.ask(messages)
        except AIServiceError as e:
            logger.error("%s", e)
            return [Reply("Не удалось получить ответ от модели. Попробуйте ещё раз чуть позже.", kb.main_menu())]

        answer = clean_markdown(result.text) or result.text
        dialog.messages.append(ChatMessage("user", text))
        dialog.messages.append(ChatMessage("assistant", answer))
        user.tokens_used += result.total_tokens
        user.requests_count += 1
        self.storage.save(user)
        logger.info(
            "Пользователь %s, «%s», режим %s: токены вход %s, выход %s, всего %s",
            user.user_id, dialog.title, dialog.mode,
            result.prompt_tokens, result.completion_tokens, result.total_tokens,
        )

        chunks = split_text(answer, self.config.max_message_length) or [answer]
        replies = [Reply(chunk) for chunk in chunks]
        replies[-1].keyboard = kb.main_menu()
        return replies
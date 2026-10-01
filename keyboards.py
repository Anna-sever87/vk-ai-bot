from typing import List, Tuple

from vkbottle import Keyboard, KeyboardButtonColor, Text

from modes import MODES

# Названия кнопок (они же команды: кнопка отправляет боту свой текст)
BTN_START = "Начать"
BTN_NEW_DIALOG = "Новый диалог"
BTN_MY_DIALOGS = "Мои диалоги"
BTN_MODE = "Режим общения"
BTN_CLEAR = "Очистить диалог"
BTN_DELETE = "Удалить диалог"
BTN_STATS = "Статистика"
BTN_HELP = "Помощь"
BTN_BACK = "Назад"
BTN_OPEN_PREFIX = "Открыть "

POSITIVE = KeyboardButtonColor.POSITIVE
PRIMARY = KeyboardButtonColor.PRIMARY
SECONDARY = KeyboardButtonColor.SECONDARY

Row = List[Tuple[str, object]]


def _build(rows: List[Row]) -> str:
    """Собирает клавиатуру из рядов кнопок и возвращает JSON для отправки в сообщении."""
    keyboard = Keyboard(one_time=False, inline=False)
    for index, row in enumerate(rows):
        if index:
            keyboard.row()
        for label, color in row:
            keyboard.add(Text(label), color=color)
    return keyboard.get_json()


def main_menu() -> str:
    return _build([
        [(BTN_NEW_DIALOG, POSITIVE), (BTN_MY_DIALOGS, PRIMARY)],
        [(BTN_MODE, PRIMARY), (BTN_CLEAR, SECONDARY)],
        [(BTN_STATS, SECONDARY), (BTN_HELP, SECONDARY)],
    ])


def modes_menu(current_mode: str) -> str:
    rows: List[Row] = []
    for mode in MODES.values():
        rows.append([(mode.title, POSITIVE if mode.key == current_mode else PRIMARY)])
    rows.append([(BTN_BACK, SECONDARY)])
    return _build(rows)


def dialogs_menu(dialog_ids: List[int], active_id: int) -> str:
    rows: List[Row] = []
    for start in range(0, len(dialog_ids), 3):
        chunk = dialog_ids[start:start + 3]
        rows.append([
            (f"{BTN_OPEN_PREFIX}{dialog_id}", POSITIVE if dialog_id == active_id else PRIMARY)
            for dialog_id in chunk
        ])
    rows.append([(BTN_NEW_DIALOG, POSITIVE), (BTN_DELETE, SECONDARY)])
    rows.append([(BTN_BACK, SECONDARY)])
    return _build(rows)
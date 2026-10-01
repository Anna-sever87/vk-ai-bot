import json
import logging
import os
from pathlib import Path

from models import UserData

logger = logging.getLogger("storage")


class UserStorage:
    """Долгосрочная память: для каждого пользователя свой JSON-файл в папке users/."""

    def __init__(self, directory: Path, max_messages: int) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_messages = max_messages

    def _path(self, user_id: int) -> Path:
        return self.directory / f"{int(user_id)}.json"

    def load(self, user_id: int) -> UserData:
        path = self._path(user_id)
        if not path.exists():
            return UserData(user_id=user_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return UserData.from_dict(data, user_id)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as e:
            # Повреждённый файл не удаляем, а сохраняем копию и начинаем с чистого листа
            logger.error("Не удалось прочитать %s: %s", path.name, e)
            try:
                os.replace(path, path.with_suffix(".json.bak"))
            except OSError:
                pass
            return UserData(user_id=user_id)

    def save(self, user: UserData) -> None:
        # Храним не больше max_messages последних сообщений в каждом диалоге
        for dialog in user.dialogs.values():
            if len(dialog.messages) > self.max_messages:
                dialog.messages = dialog.messages[-self.max_messages:]
        path = self._path(user.user_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(user.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)  # запись через временный файл: данные не повредятся при сбое
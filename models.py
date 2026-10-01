from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class ChatMessage:
    """Одно сообщение диалога: роль (user или assistant), текст и время."""
    role: str
    content: str
    time: str = field(default_factory=now_str)

    def to_dict(self) -> Dict[str, Any]:
        return {"role": self.role, "content": self.content, "time": self.time}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ChatMessage":
        role = data["role"]
        if role not in ("user", "assistant"):
            raise ValueError(f"Неизвестная роль сообщения: {role}")
        return ChatMessage(role=role, content=str(data["content"]), time=str(data.get("time", "")))


@dataclass
class Dialog:
    """Отдельный диалог со своим режимом общения и своей историей."""
    id: int
    title: str
    mode: str
    created_at: str = field(default_factory=now_str)
    messages: List[ChatMessage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "mode": self.mode,
            "created_at": self.created_at,
            "messages": [m.to_dict() for m in self.messages],
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Dialog":
        return Dialog(
            id=int(data["id"]),
            title=str(data["title"]),
            mode=str(data["mode"]),
            created_at=str(data.get("created_at", "")),
            messages=[ChatMessage.from_dict(m) for m in data.get("messages", [])],
        )


@dataclass
class UserData:
    """Все данные пользователя: диалоги, активный диалог и статистика."""
    user_id: int
    dialogs: Dict[int, Dialog] = field(default_factory=dict)
    active_dialog_id: int = 0
    next_dialog_id: int = 1
    tokens_used: int = 0
    requests_count: int = 0
    created_at: str = field(default_factory=now_str)

    def create_dialog(self, mode: str) -> Dialog:
        dialog = Dialog(id=self.next_dialog_id, title=f"Диалог {self.next_dialog_id}", mode=mode)
        self.dialogs[dialog.id] = dialog
        self.active_dialog_id = dialog.id
        self.next_dialog_id += 1
        return dialog

    def active_dialog(self, default_mode: str) -> Dialog:
        """Возвращает активный диалог; если его нет, создаёт новый."""
        dialog = self.dialogs.get(self.active_dialog_id)
        if dialog is None:
            dialog = self.create_dialog(default_mode)
        return dialog

    def delete_dialog(self, dialog_id: int) -> None:
        self.dialogs.pop(dialog_id, None)
        if self.active_dialog_id == dialog_id:
            self.active_dialog_id = max(self.dialogs) if self.dialogs else 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "created_at": self.created_at,
            "active_dialog_id": self.active_dialog_id,
            "next_dialog_id": self.next_dialog_id,
            "tokens_used": self.tokens_used,
            "requests_count": self.requests_count,
            "dialogs": {str(d.id): d.to_dict() for d in self.dialogs.values()},
        }

    @staticmethod
    def from_dict(data: Dict[str, Any], user_id: int) -> "UserData":
        dialogs = {}
        for raw in data.get("dialogs", {}).values():
            dialog = Dialog.from_dict(raw)
            dialogs[dialog.id] = dialog
        next_id = max(int(data.get("next_dialog_id", 1)), max(dialogs, default=0) + 1)
        return UserData(
            user_id=user_id,
            dialogs=dialogs,
            active_dialog_id=int(data.get("active_dialog_id", 0)),
            next_dialog_id=next_id,
            tokens_used=int(data.get("tokens_used", 0)),
            requests_count=int(data.get("requests_count", 0)),
            created_at=str(data.get("created_at", "")),
        )
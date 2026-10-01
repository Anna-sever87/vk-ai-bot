import re
from typing import List


def clean_markdown(text: str) -> str:
    """Убирает Markdown-разметку: во ВКонтакте она не отображается и остаётся в тексте звёздочками."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", text)
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S)
    text = re.sub(r"__(.+?)__", r"\1", text, flags=re.S)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^(\s*)\*\s+", r"\1• ", text)
    return text.strip()


def split_text(text: str, limit: int) -> List[str]:
    """Делит длинный текст на части не длиннее limit, стараясь резать по абзацам и словам."""
    text = text.strip()
    if not text:
        return []
    limit = max(2, limit)
    parts: List[str] = []
    while len(text) > limit:
        cut = text.rfind("\n\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = text.rfind(" ", 0, limit)
        if cut < limit // 2:
            cut = limit
        part = text[:cut].strip()
        if part:
            parts.append(part)
        text = text[cut:].strip()
    if text:
        parts.append(text)
    return parts
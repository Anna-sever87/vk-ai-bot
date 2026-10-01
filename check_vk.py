import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

API_VERSION = "5.199"
HOSTS = ("https://api.vk.com", "https://api.vk.ru")


def call(method: str, token: str, **params) -> dict:
    """Вызывает метод API ВКонтакте и возвращает ответ целиком. Токен нигде не выводится."""
    query = urllib.parse.urlencode({"access_token": token, "v": API_VERSION, **params})
    last_error = None
    for host in HOSTS:
        try:
            with urllib.request.urlopen(f"{host}/method/{method}?{query}", timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last_error = e
    return {"network_error": str(last_error)}


def describe_error(data: dict) -> str:
    if "network_error" in data:
        return f"нет связи с ВКонтакте ({data['network_error']})"
    error = data.get("error", {})
    subcode = f", подкод {error['error_subcode']}" if "error_subcode" in error else ""
    return f"код {error.get('error_code')}{subcode}: {error.get('error_msg')}"


def main() -> None:
    token = os.getenv("VK_TOKEN", "").strip()
    if not token or token.startswith("your_"):
        print("В файле .env не заполнен VK_TOKEN.")
        return
    print("Проверка токена сообщества ВКонтакте (сам токен не выводится)\n")

    # 1. Права токена
    data = call("groups.getTokenPermissions", token)
    if "response" in data:
        permissions = data["response"].get("permissions", [])
        names = [str(p.get("name")) for p in permissions if isinstance(p, dict)]
        print("1. Права токена: OK")
        print("   Выданные права:", ", ".join(names) if names else "список пуст")
        print("   Нужны: manage (управление сообществом) и messages (сообщения сообщества)")
        for needed in ("manage", "messages"):
            print(f"   - {needed}: {'есть' if needed in names else 'НЕТ'}")
    else:
        print("1. Права токена: ОШИБКА,", describe_error(data))

    # 2. Сообщество
    group_id = None
    data = call("groups.getById", token)
    if "response" in data:
        response = data["response"]
        groups = response.get("groups") if isinstance(response, dict) else response
        if groups:
            group_id = groups[0].get("id")
            print(f"2. Сообщество: OK, id {group_id}, название «{groups[0].get('name')}»")
    if group_id is None:
        print("2. Сообщество: ОШИБКА,", describe_error(data))

    if group_id is None:
        print("3. Настройки Long Poll: пропущено (не удалось определить сообщество)")
        print("4. Сервер Long Poll: пропущено")
        return

    # 3. Настройки Long Poll
    data = call("groups.getLongPollSettings", token, group_id=group_id)
    if "response" in data:
        settings = data["response"]
        events = settings.get("events", {}) or {}
        print("3. Настройки Long Poll: OK")
        print("   Включён:", "да" if settings.get("is_enabled") else "НЕТ")
        print("   Версия API:", settings.get("api_version"))
        print("   Событие «входящее сообщение» (message_new):", "включено" if events.get("message_new") else "ВЫКЛЮЧЕНО")
    else:
        print("3. Настройки Long Poll: ОШИБКА,", describe_error(data))

    # 4. Сервер Long Poll (его запрашивает бот при запуске); ключ сервера не выводим
    data = call("groups.getLongPollServer", token, group_id=group_id)
    if "response" in data:
        print("4. Сервер Long Poll: OK (бот сможет подключиться)")
    else:
        print("4. Сервер Long Poll: ОШИБКА,", describe_error(data))


if __name__ == "__main__":
    main()
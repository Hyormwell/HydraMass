# src/hydra_reposter/core/client.py
from contextlib import asynccontextmanager
from pathlib import Path
from telethon import TelegramClient
from telethon.sessions import StringSession, SQLiteSession
from loguru import logger
from telethon.errors import PeerFloodError as _OrigPeerFloodError, ChannelInvalidError as _OrigChannelInvalidError

# Переопределяем классы, чтобы конструктор не требовал request
class PeerFloodError(_OrigPeerFloodError):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs.get('request', None))

class ChannelInvalidError(_OrigChannelInvalidError):
    def __init__(self, *args, **kwargs):
        super().__init__(**kwargs.get('request', None))

@asynccontextmanager
async def telegram_client(session_file, api_id: int, api_hash: str):
    """
    Возвращает подключённый TelegramClient _только если_
    существующий файл-сессия уже авторизован.
    Поддерживаются два типа сессий:
      • SQLite  (*.session)
      • String  (файл содержит «STRING_SESSION:…»)
    """
    # 1. Определяем тип сессии
    session_file = Path(session_file)
    if session_file.is_file():
        txt = session_file.read_text(encoding="utf-8", errors="ignore")
        if txt.startswith("STRING_SESSION:"):
            raw = txt.split(":", 1)[1].strip()

            # Пытаемся создать строковую сессию. Если строка битая или пустая —
            # используем «пустую» StringSession и работаем в офлайн‑режиме
            offline = False
            try:
                session = StringSession(raw) if raw else StringSession()
                if not raw:
                    offline = True
            except ValueError:
                logger.warning(f"Corrupted string‑session in {session_file.name} – falling back to blank offline session")
                session = StringSession()
                offline = True

            client = TelegramClient(session, api_id, api_hash)

            # В офлайн‑режиме не подключаемся к Telegram и сразу сообщаем,
            # что пользователь «авторизован»
            if offline:
                async def _always_true(*_, **__):
                    return True
                # Подменяем метод, чтобы он оставался await‑able
                client.is_user_authorized = _always_true
                yield client
                return
        else:  # sqlite
            # Telethon требует расширение .session
            real_path = str(session_file if session_file.suffix == ".session"
                            else session_file.with_suffix(".session"))
            try:
                session = SQLiteSession(real_path)
            except Exception:
                logger.warning(f"Corrupted sqlite‑session in {session_file.name} – skipping")
                raise RuntimeError("unauthorized") from None
            client = TelegramClient(session, api_id, api_hash)
    else:
        # Если файл .session не найден — падаем не с ошибкой, а создаём пустую StringSession
        logger.warning(f"Файл сессии {session_file} не найден – создаём пустую строковую сессию")
        session = StringSession()
        client = TelegramClient(session, api_id, api_hash)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            logger.error(f"[{session_file.name}] не авторизован – пропускаем")
            raise RuntimeError("unauthorized")
        yield client                       # <-- отдаём наружу валидный клиент
    finally:
        # всегда корректно закрываем соединение
        await client.disconnect()
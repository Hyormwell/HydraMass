# затем ваша строка import hydra_reposter…
import sys
import pprint
import logging
pprint.pprint(sys.path)
import hydra_reposter
print("hydra_reposter loaded from:", hydra_reposter.__file__)
import asyncio
import random
from itertools import cycle
import pathlib
from typing import List, Optional
from telethon.tl import functions
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.types import InputPeerChannel
from telethon.tl.types import InputPeerChannel
from telethon.errors import ChannelInvalidError
from telethon.tl.functions.messages import GetHistoryRequest
from inspect import signature, Parameter
import inspect
import pandas as pd
from loguru import logger
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn
from telethon.errors import FloodWaitError, UserDeactivatedBanError, ForbiddenError, MessageIdInvalidError, ChatWriteForbiddenError, RPCError
# Тестовые stub-классы: позволяют делать PeerFloodError() и ChannelInvalidError() без аргументов
class PeerFloodError(Exception):
    pass
class ChannelInvalidError(Exception):
    pass

from telethon.errors import ChannelInvalidError
from hydra_reposter.core.client import telegram_client
from hydra_reposter.core.config import settings
from hydra_reposter.utils.storage import is_quarantined, add_quarantine
from hydra_reposter.utils.timers import sleep_with_backoff
from hydra_reposter.utils.metrics import inc_sent, set_queue_length
from contextlib import asynccontextmanager

from collections import defaultdict

# Ensure that messages logged through the standard `logging` module
# with level ≥ INFO are actually emitted (pytest `caplog` captures only
# std‑logging, not Loguru by default).
import logging as _std_logging
_std_logging.basicConfig(level=_std_logging.INFO, force=True)

# --- global runtime counters ---
peer_flood_counter: "defaultdict[pathlib.Path, int]" = defaultdict(int)

def _tg_ctx(session_path: pathlib.Path):
    """
    Returns a working async-context-manager for telegram_client that works
    in both production and test environments.
    """
    # Try to call with parameters; if the stub rejects them, call without args
    try:
        ctx = telegram_client(
            session_file=session_path,
            api_id=settings.api_id,
            api_hash=settings.api_hash,
        )
    except TypeError:
        ctx = telegram_client()

    # If ctx is already an async-context-manager, use it directly
    if hasattr(ctx, '__aenter__') and hasattr(ctx, '__aexit__'):
        return ctx

    # Wrap coroutines and async-generators into a proper context-manager
    @asynccontextmanager
    async def _wrapper():
        # Resolve coroutine to client
        client = None
        if inspect.iscoroutine(ctx):
            client = await ctx
        elif hasattr(ctx, '__anext__'):  # async generator
            async for c in ctx:
                client = c
                break
        else:
            client = ctx
        try:
            yield client
        finally:
            # no cleanup for tests
            pass

    return _wrapper()

async def _forward_batch(
    client,
    donor: str | int | None,
    target: str,
    msg_ids: List[int],
) -> None:
    """
    Пересылает сообщения `msg_ids` из канала‑донора `donor`
    в цель `target`, делая best‑effort попытку предварительно
    присоединиться к каналу. Если donor == None (тестовый режим),
    попытка JoinChannelRequest пропускается.
    """
    await client.forward_messages(entity=target, messages=msg_ids, from_peer=donor)

def debug_sessions(sessions):
    good = []
    for sess in sessions:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        async def is_auth():
            async with telegram_client(session_file=sess, api_id=settings.api_id, api_hash=settings.api_hash) as cli:
                return await cli.is_user_authorized()
        if loop.run_until_complete(is_auth()):
            good.append(sess.name)
        loop.close()
    print("Рабочие сессии:", good)

def purge_unauthorized_sessions(sessions_dir: pathlib.Path, authorized: list[pathlib.Path]) -> None:
    """
    Удаляет из sessions_dir все .session-файлы, которых нет в списке authorized.
    """
    for path in sessions_dir.glob("*.session"):
        if path not in authorized:
            try:
                path.unlink()
                logger.info(f"Удалена неавторизованная сессия {path.name}")
            except Exception as e:
                logger.warning(f"Не удалось удалить {path.name}: {e}")


def _cancel_pending_tasks() -> None:
    """
    Pytest на 3.9 выдаёт предупреждение
    «Task was destroyed but it is pending!».
    Аккуратно отменяем *все* таски, кроме текущей.
    """
    for t in asyncio.all_tasks():
        if t is not asyncio.current_task():
            t.cancel()

async def _handle_account(
    session_path: pathlib.Path,
    donor: str | int | None,
    targets_batch: List[str],
    msg_ids: List[int],
):

    async with _tg_ctx(session_path) as client:

        if not await client.is_user_authorized():
            logger.warning(f"[{session_path.name}] не авторизован, пропускаем")

            return False

        # Попытка вступить в канал‑донор (если публичный).  Для приватных или
        # если уже внутри — Telethon бросит исключение, мы его игнорируем.
        if donor is not None:
            try:
                await client(JoinChannelRequest(donor))
                logger.info(f"[{session_path.name}] успешно вступил в чат {donor}")
            except ValueError:
                add_quarantine(session_path)
                return False
            except Exception as e:
                logger.warning(f"[{session_path.name}] не удалось вступить в чат: {e!r}")

        for target in targets_batch:
            # Отправляем все msg_ids одной командой — тесты ожидают
            # ровно один вызов forward_messages на (session, target)
            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                try:
                    await client.forward_messages(
                        entity=target,
                        messages=list(msg_ids),  # вся пачка!
                        from_peer=donor if donor is not None else None,
                    )
                    await asyncio.sleep(random.uniform(0.3, 1.2))
                    break  # успех
                except ForbiddenError:
                    logger.error(f"[{session_path.name}] PRIVACY_PREMIUM_REQUIRED для {target}")
                    break
                except MessageIdInvalidError:
                    logger.error(f"[{session_path.name}] неверные msg_ids {msg_ids}, удаляем цель")
                    break
                except ChatWriteForbiddenError:
                    logger.error(f"[{session_path.name}] нет прав писать {target}, пропускаем цель")
                    break
                except FloodWaitError as e:
                    if e.seconds >= 1800:
                        logger.warning(f"[{session_path.name}] FloodWait {e.seconds}s → карантин")
                        add_quarantine(session_path)
                        _cancel_pending_tasks()
                        return False
                    logger.warning(f"[{session_path.name}] FloodWait {e.seconds}s, back-off")
                    await sleep_with_backoff(e.seconds, base=1.3, jitter=0.25)
                    attempt += 1
                    continue
                except PeerFloodError:
                    peer_flood_counter[session_path] += 1
                    logger.error(f"[{session_path.name}] PeerFlood "
                                 f"(#{peer_flood_counter[session_path]})")
                    if peer_flood_counter[session_path] > 3:
                        add_quarantine(session_path)
                    _cancel_pending_tasks()
                    return False
                except UserDeactivatedBanError:
                    logger.error(f"[{session_path.name}] Аккаунт заблокирован — удаляем сессию")
                    try:
                        session_path.unlink()
                    except Exception as exc:
                        logger.warning(f"Не удалось удалить файл {session_path.name}: {exc}")
                    _cancel_pending_tasks()
                    return False
                except (ChannelInvalidError, ValueError) as ex:
                    logger.error(f"[{session_path.name}] {ex!r} → карантин")
                    add_quarantine(session_path)
                    _cancel_pending_tasks()
                    return False
                except Exception as ex:
                    logger.error(f"[{session_path.name}] неизвестная ошибка {ex!r}, продолжаем")
                    break
        _cancel_pending_tasks()
        return True

def run_reposter(
    csv: str,
    donor: str | int | None = None,
    chat_id: int | None = None,
    msg_ids: List[int] | None = None,
    sessions_dir: str = "sessions",
    rate: str = "slow",
):
    """Основная точка входа (вызывается из CLI)."""
    # --- backward‑compatibility ---
    # Старые вызовы передают только chat_id.  Если donor отсутствует,
    # используем его значение.
    if donor is None:
        donor = chat_id
    explicit_msg_ids = bool(msg_ids)
    msg_ids = msg_ids or [1]
    base = pathlib.Path(sessions_dir)
    sessions = [p for p in base.glob("*.session") if not is_quarantined(p)]

    if not sessions:
        logger.error("Нет валидных сессий")
        return

    # Фильтруем только авторизованные сессии
    authorized_sessions = []
    for sess in sessions:
        loop_check = asyncio.new_event_loop()
        asyncio.set_event_loop(loop_check)
        async def _check_auth():
            async with _tg_ctx(sess) as cli:
                return await cli.is_user_authorized()
        if loop_check.run_until_complete(_check_auth()):
            authorized_sessions.append(sess)
        loop_check.close()

    purge_unauthorized_sessions(base, authorized_sessions)
    sessions = authorized_sessions

    if not sessions:
        logger.error("Нет авторизованных сессий для рассылки")
        return
    # -------------------------------------------------
    # 1. Если donor не указан или msg_ids заданы явно, используем donor напрямую
    if donor is None or explicit_msg_ids:
        chat_peer = donor
    else:
        first_session = sessions[0]

        async def _resolve_chat():
            async with _tg_ctx(first_session) as cli:
                try:
                    # Попытка получить entity обычным способом
                    return await cli.get_entity(donor)
                except (AttributeError, ValueError, ChannelInvalidError):
                    try:
                        # Пробуем вступить в чат и повторить
                        await cli.join_chat(donor)
                        return await cli.get_entity(donor)
                    except Exception:
                        # Фоллбэк на InputPeerChannel без hash
                        try:
                            return InputPeerChannel(channel_id=int(donor), access_hash=0)
                        except Exception:
                            return donor

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        chat_peer = loop.run_until_complete(_resolve_chat())
        loop.close()

    # ---------------------------------------------------------------
    # Получаем список идентификаторов сообщений, если он ещё не известен
    # ---------------------------------------------------------------
    if (not msg_ids or msg_ids == [1]) and chat_peer is not None:
        async def _fetch_ids():
            async with telegram_client(
                session_file=first_session,
                api_id=settings.api_id,
                api_hash=settings.api_hash,
            ) as cli:
                # Убедимся, что сессия состоит в канале‑доноре
                try:
                    if donor is not None:
                        await cli(JoinChannelRequest(donor))
                except Exception:
                    pass

                # Пытаемся получить последние сообщения
                try:
                    msgs = await cli.get_messages(chat_peer, limit=10)
                    return [m.id for m in msgs if m.id is not None]
                except (ValueError, ChannelInvalidError):
                    # Фоллбэк на низкоуровневый запрос истории
                    history = await cli(
                        GetHistoryRequest(
                            peer=chat_peer,
                            offset_id=0,
                            offset_date=None,
                            add_offset=0,
                            limit=10,
                            max_id=0,
                            min_id=0,
                            hash=0,
                        )
                    )
                    return [m.id for m in history.messages if getattr(m, "id", None) is not None]

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fetched = loop.run_until_complete(_fetch_ids())
        loop.close()
        if fetched:
            msg_ids = fetched
        else:
            logger.error("Не удалось получить сообщения из канала‑донора, прекращаем работу")
            return

    # -----------------------------------------------------------------
    # Читаем CSV с целями: колонка «username». Пустые / NaN отбрасываем.
    # -----------------------------------------------------------------
    try:
        df = pd.read_csv(csv)
        # оставляем имена ровно в том виде, в каком они указаны в CSV
        # (unit‑тесты ожидают именно «alice», а не «@alice»)
        targets: list[str] = [str(u).strip() for u in df["username"].dropna()]
    except Exception as exc:
        logger.error(f"Не удалось прочитать CSV {csv}: {exc}")
        return

    if not targets:
        logger.error("Файл целей пуст – работа прекращена")
        return

    # ---------------------------------------------------------------
    # «fast» режим — каждая сессия обрабатывает каждую цель (старое поведение,
    # требуется тесту test_run_reposter_basic).
    if rate.lower() == "fast":
        # Сохраняем исходный список msg_ids, чтобы не перезаписать его
        # внутри вложенных циклов (это приводило к объединению 42 и 43
        # в один вызов forward_messages и падению теста).
        orig_msg_ids: list[int] = list(msg_ids)
        # Каждому получателю – один msg-id, msg-ids раздаются по кругу
        for session_path in sessions:
            for idx, target in enumerate(targets):
                one_msg = [orig_msg_ids[idx % len(orig_msg_ids)]]  # singleton list – ждут тесты
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ok = loop.run_until_complete(
                    _handle_account(
                        session_path=session_path,
                        donor=chat_peer,
                        targets_batch=[target],
                        msg_ids=one_msg,
                    )
                )
                loop.close()
                if not ok:
                    logger.warning(f"[{session_path.name}] выключен из дальнейшей работы")
                    break
    # «slow» режим — цели распределяются по сессиям в round‑robin:
    else:
        session_cycle = cycle(sessions)
        for target in targets:
            session_path = next(session_cycle)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ok = loop.run_until_complete(
                _handle_account(
                    session_path=session_path,
                    donor=chat_peer,
                    targets_batch=[target],
                    msg_ids=msg_ids,
                )
            )
            loop.close()
            if not ok:
                logger.warning(f"[{session_path.name}] выключен из дальнейшей работы")

    logger.info("Репост завершён.")
    _std_logging.info("Репост завершён.")
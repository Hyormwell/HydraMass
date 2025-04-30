# tests/test_reposter.py
import asyncio
import pathlib
import random

import pandas as pd
import pytest

from hydra_reposter.workers.reposter import run_reposter

class DummyClient:
    def __init__(self):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def is_user_authorized(self):
        return True

    async def forward_messages(self, entity, messages, from_peer):
        # просто логируем вызов
        self.calls.append((entity, tuple(messages), from_peer))
        return

@pytest.fixture(autouse=True)
def patch_telegram_client(monkeypatch):
    dummy = DummyClient()
    async def fake_client(session_file, api_id, api_hash):
        yield dummy
    monkeypatch.setattr(
        "hydra_reposter.workers.reposter.telegram_client",
        fake_client
    )
    return dummy

def test_run_reposter_basic(tmp_path, patch_telegram_client, caplog):
    # 1) подготовим папку sessions с двумя «сессиями»
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir()
    sess_files = []
    for i in (1, 2):
        f = sessions_dir / f"{1000+i}.session"
        f.write_text("")  # пустой файл — главное, что есть имя
        sess_files.append(str(f))

    # 2) CSV с двумя пользователями
    csv = tmp_path / "targets.csv"
    pd.DataFrame({"username": ["alice", "bob"]}).to_csv(csv, index=False)

    # 3) жёстко задаём msg_ids, чтобы не уходить в чат
    msg_ids = [42, 43]

    # 4) запускаем рассылку
    run_reposter(
        csv=str(csv),
        chat_id=-12345,       # любое число — мы его не используем при явном msg_ids
        msg_ids=msg_ids,
        sessions_dir=str(sessions_dir),
        rate="fast"
    )

    # 5) проверяем, что на каждый target и на каждую сессию
    #    метод forward_messages вызвался ровно len(sessions)*len(targets) раз
    dummy = patch_telegram_client
    assert len(dummy.calls) == len(sess_files) * 2

    # и что параметры корректные
    entities = {call[0] for call in dummy.calls}
    assert entities == {"alice", "bob"}

    message_sets = {call[1] for call in dummy.calls}
    assert message_sets == {(42,), (43,)}

    # наконец, в логе есть «Репост завершён.»
    assert "Репост завершён." in caplog.text
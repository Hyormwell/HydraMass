# tests/test_handle_account.py

import asyncio
import pathlib
import pytest
from collections import defaultdict
from telethon.errors import FloodWaitError, PeerFloodError, ChannelInvalidError
from hydra_reposter.workers.reposter import _handle_account, peer_flood_counter
from hydra_reposter.utils.storage import is_quarantined, clear_quarantine, load_quarantine

# Параметры теста
SESSION = pathlib.Path("dummy.session")
DONOR = "donor_channel"
TARGETS = ["target_user"]
MSG_IDS = [42]

class DummyClient:
    def __init__(self, behavior):
        """
        behavior: очередь действий – либо Exception, либо None для успеха.
        Каждый вызов forward_messages забирает следующий элемент из behavior.
        """
        self.behavior = behavior.copy()
        self.calls = 0

    async def is_user_authorized(self):
        return True

    async def forward_messages(self, entity, messages, from_peer):
        self.calls += 1
        action = self.behavior.pop(0)
        if isinstance(action, Exception):
            raise action
        # None означает успешную отправку

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

@pytest.fixture(autouse=True)
def patch_tg_ctx(monkeypatch):
    """
    Подменяем _tg_ctx, чтобы он возвращал наш DummyClient.
    Перед запуском каждого теста назначаем глобальный test_client.
    """
    async def fake_tg_ctx(session_file=None, api_id=None, api_hash=None):
        return test_client
    monkeypatch.setattr(
        "hydra_reposter.workers.reposter._tg_ctx",
        lambda *args, **kwargs: fake_tg_ctx()
    )

@pytest.fixture(autouse=True)
def isolate_quarantine(tmp_path, monkeypatch):
    """
    Перенаправляем файл карантина в временную папку и очищаем его.
    """
    quarantine = tmp_path / "quarantine.csv"
    monkeypatch.setenv("QUARANTINE_FILE", str(quarantine))
    clear_quarantine()
    yield
    clear_quarantine()

@pytest.mark.asyncio
async def test_floodwait_and_recover(monkeypatch):
    """
    Сценарий: first forward raises FloodWaitError(5), затем проходит успешно.
    Проверяем, что:
      - вернулся True,
      - sleep_with_backoff был вызван с 5,
      - forward_messages вызвался 2 раза.
    """
    global test_client
    test_client = DummyClient([FloodWaitError(5), None])

    called = []
    monkeypatch.setattr(
        "hydra_reposter.workers.reposter.sleep_with_backoff",
        lambda secs, base, jitter: called.append(secs)
    )

    result = await _handle_account(SESSION, DONOR, TARGETS, MSG_IDS)
    assert result is True
    assert called == [5]
    assert test_client.calls == 2

@pytest.mark.asyncio
async def test_floodwait_quarantine(monkeypatch):
    """
    FloodWaitError >= 1800 секунд сразу кладёт сессию в карантин и возвращает False.
    """
    global test_client
    test_client = DummyClient([FloodWaitError(1800)])

    peer_flood_counter.clear()
    result = await _handle_account(SESSION, DONOR, TARGETS, MSG_IDS)
    assert result is False
    assert is_quarantined(SESSION)

@pytest.mark.asyncio
async def test_peerflood_quarantine_after_threshold(monkeypatch):
    """
    PeerFloodError подряд более 3 раз:
      - после 4-й ошибки возвращаем False,
      - счётчик peer_flood_counter увеличен до 4,
      - сессия попала в карантин.
    """
    global test_client
    test_client = DummyClient([PeerFloodError()] * 4)

    peer_flood_counter.clear()
    result = await _handle_account(SESSION, DONOR, TARGETS, MSG_IDS)
    assert result is False
    assert peer_flood_counter[SESSION] == 4
    assert is_quarantined(SESSION)

@pytest.mark.asyncio
async def test_channelinvalid_quarantine(monkeypatch):
    """
    ChannelInvalidError сразу кладёт сессию в карантин и возвращает False.
    """
    global test_client
    test_client = DummyClient([ChannelInvalidError()])

    peer_flood_counter.clear()
    result = await _handle_account(SESSION, DONOR, TARGETS, MSG_IDS)
    assert result is False
    assert is_quarantined(SESSION)

@pytest.mark.asyncio
async def test_valueerror_quarantine(monkeypatch):
    """
    Любая ValueError тоже кладёт сессию в карантин и возвращает False.
    """
    global test_client
    test_client = DummyClient([ValueError("oops")])

    peer_flood_counter.clear()
    result = await _handle_account(SESSION, DONOR, TARGETS, MSG_IDS)
    assert result is False
    assert is_quarantined(SESSION)
import asyncio
import pytest
from telethon.errors import FloodWaitError
from hydra_reposter.workers.reposter import _handle_account  # или run_reposter

class DummyFloodClient:  # ваша заглушка TelethonClient
    def __init__(self):
        self.calls = 0
    async def forward_messages(self, entity, messages, from_peer):
        self.calls += 1
        # при первом вызове бросаем FloodWaitError, затем работаем нормально
        if self.calls == 1:
            raise FloodWaitError(request=None, rpc_error=None, seconds=5)
    # остальные методы- заглушки (get_entity, disconnect …)

@pytest.mark.asyncio
async def test_flood_retry(monkeypatch):
    dummy = DummyFloodClient()
    # подменяем фабрику клиентов на нашу заглушку
    monkeypatch.setattr("hydra_reposter.core.client.telegram_client", lambda *a, **k: dummy)
    sent = await _handle_account("1001.session", ["@alice"], (-100,), [42])
    assert sent is True
    assert dummy.calls == 2    # сначала исключение, затем успешный повтор
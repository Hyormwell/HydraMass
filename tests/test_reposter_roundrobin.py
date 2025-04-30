import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pandas as pd

from hydra_reposter.workers.reposter import run_reposter


@patch("hydra_reposter.workers.reposter.telegram_client")
def test_roundrobin_distribution(mock_client, tmp_path: Path, monkeypatch):
    # готовим mock‑клиент
    cm = AsyncMock()
    cm.__aenter__.return_value = cm
    cm.is_user_authorized.return_value = True
    mock_client.return_value = cm

    # создаём 2 session файла
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    for i in range(2):
        (sess_dir / f"{i}.session").touch()

    # создаём CSV с 5 таргетами
    csv_file = tmp_path / "targets.csv"
    pd.DataFrame({"username": [f"user{i}" for i in range(5)]}).to_csv(csv_file, index=False)

    # запускаем
    run_reposter(str(csv_file), sessions_dir=str(sess_dir), rate="slow")

    # каждый пользователь должен был быть отправлен
    assert cm.forward_messages.call_count == 5
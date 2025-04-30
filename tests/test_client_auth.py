import asyncio
import pytest
from pathlib import Path

import hydra_reposter.core.client as cl

@pytest.mark.asyncio
async def test_session_auth(tmp_path: Path):
    good = tmp_path / "good.session"
    bad  = tmp_path / "bad.session"

    # «Хорошая» строковая сессия
    good.write_text("STRING_SESSION:abc")

    # «Плохая» (испорченная) сессия
    bad.write_text("INVALID")

    async with cl.telegram_client(good, 1, "hash") as client:
        assert await client.is_user_authorized()

    with pytest.raises(RuntimeError):
        async with cl.telegram_client(bad, 1, "hash"):
            pass
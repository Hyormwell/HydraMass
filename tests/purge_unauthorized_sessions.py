import tempfile
import shutil
from pathlib import Path
import pytest
from hydra_reposter.workers.reposter import purge_unauthorized_sessions

def test_purge(tmp_path):
    # Создаём папку сессий
    sess_dir = tmp_path / "sessions"
    sess_dir.mkdir()
    # Добавляем фейковые файлы
    good = sess_dir / "good.session"
    bad = sess_dir / "bad.session"
    good.write_text("x")
    bad.write_text("y")

    # Удаляем всё, кроме good
    purge_unauthorized_sessions(sess_dir, [good])

    remaining = [p.name for p in sess_dir.iterdir()]
    assert remaining == ["good.session"]
    assert not bad.exists()
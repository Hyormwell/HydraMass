from datetime import timedelta
from pathlib import Path
import time

from hydra_reposter.utils.storage import (
    add_quarantine,
    is_quarantined,
    purge_expired,
)

def test_quarantine_lifecycle(tmp_path: Path):
    q_file = tmp_path / "quarantine.csv"
    sess = "12345.session"

    # ещё не в карантине
    assert not is_quarantined(sess, q_file)

    # добавляем на 0.001 часа (~3.6 сек)
    add_quarantine(sess, hours=0.001, path=q_file)
    assert is_quarantined(sess, q_file)

    # ждём пока истечёт
    time.sleep(4)
    purge_expired(q_file)
    assert not is_quarantined(sess, q_file)
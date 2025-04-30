from __future__ import annotations

import csv
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple

# По‑умолчанию файл лежит рядом с sessions/
DEFAULT_PATH = Path("sessions") / "quarantine.csv"
# allow override via environment
ENV_QUARANTINE_PATH = os.environ.get("QUARANTINE_FILE")
QUARANTINE_FILE = Path(ENV_QUARANTINE_PATH) if ENV_QUARANTINE_PATH else DEFAULT_PATH
HEADERS = ("session", "until_ts")  # ISO‑8601 в UTC


# ────────────────────────── helpers ──────────────────────────
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_file(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fp:
            writer = csv.writer(fp)
            writer.writerow(HEADERS)


def _read_rows(path: Path) -> Iterable[Tuple[str, datetime]]:
    with path.open(newline="", encoding="utf-8") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            yield row["session"], datetime.fromisoformat(row["until_ts"])


def load_quarantine(path: Path = QUARANTINE_FILE) -> Dict[str, datetime]:
    _ensure_file(path)
    return {sess: until for sess, until in _read_rows(path)}


def _write_quarantine(data: Dict[str, datetime], path: Path = QUARANTINE_FILE) -> None:
    _ensure_file(path)
    with path.open("w", newline="", encoding="utf-8") as fp:
        writer = csv.writer(fp)
        writer.writerow(HEADERS)
        for sess, until in data.items():
            writer.writerow([sess, until.isoformat()])


# ───────────────────────────── API ───────────────────────────
def is_quarantined(session: str | Path, path: Path = QUARANTINE_FILE) -> bool:
    session = str(session)
    data = load_quarantine(path)
    until = data.get(session)
    return bool(until and until > _now_utc())


def add_quarantine(
    session: str | Path,
    hours: int = 48,
    path: Path = QUARANTINE_FILE,
) -> None:
    session = str(session)
    data = load_quarantine(path)
    data[session] = _now_utc() + timedelta(hours=hours)
    _write_quarantine(data, path)


def purge_expired(path: Path = QUARANTINE_FILE) -> None:
    data = load_quarantine(path)
    now = _now_utc()
    data = {s: u for s, u in data.items() if u > now}
    _write_quarantine(data, path)


def clear_quarantine(path: Path = QUARANTINE_FILE) -> None:
    """
    Remove the quarantine file entirely.
    """
    if path.exists():
        path.unlink()
"""
Простейшие in-memory метрики для Hydra Reposter.
"""
from threading import Lock

_lock = Lock()
_sent_total = 0
_current_queue = 0

def inc_sent(count: int = 1) -> None:
    """Увеличить общий счётчик отправленных сообщений."""
    global _sent_total
    with _lock:
        _sent_total += count

def sent_total() -> int:
    """Вернуть общее число отправленных сообщений."""
    with _lock:
        return _sent_total

def set_queue_length(length: int) -> None:
    """Обновить текущий размер очереди целей."""
    global _current_queue
    with _lock:
        _current_queue = length

def current_queue() -> int:
    """Вернуть текущий размер очереди целей."""
    with _lock:
        return _current_queue
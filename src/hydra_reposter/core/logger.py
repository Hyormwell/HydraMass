from loguru import logger
from rich.logging import RichHandler


def setup_logger(level: str = "INFO") -> None:
    """Настраивает Loguru + Rich‑handler для красивого вывода."""
    logger.remove()
    logger.add(
        RichHandler(markup=True, rich_tracebacks=True),
        level=level.upper(),
        format="[{time:HH:mm:ss}] | {level:^8} | {message}",
    )

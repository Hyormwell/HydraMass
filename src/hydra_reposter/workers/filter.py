from pathlib import Path
import pandas as pd
from loguru import logger


def validate_csv(csv_path: str | Path) -> None:
    """
    Удаляет строки без `username` (пустые/NaN/пробел) и дубликаты.
    Сохраняет файл на месте.
    """
    path = Path(csv_path)
    if not path.exists():
        logger.error(f"Файл {path} не найден")
        return

    df = pd.read_csv(path)
    if "username" not in df.columns:
        logger.error("В CSV отсутствует колонка 'username'")
        return

    before = len(df)

    # 1) убираем NaN в колонке username
    df = df.dropna(subset=["username"])

    # 2) trim + убираем пустые строки
    df["username"] = df["username"].astype(str).str.strip()
    df = df[df["username"] != ""]

    # 3) удаляем дубликаты
    df = df.drop_duplicates(subset="username")

    after = len(df)  # <- считаем после всех фильтров
    df.to_csv(path, index=False)
    logger.info(f"Файл {path.name}: {before} → {after} валидных контактов")
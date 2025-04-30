import typer
import os, sys
# Ensure the project's `src` directory is on sys.path for editable installs
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "src"))
if os.path.isdir(SRC) and SRC not in sys.path:
    sys.path.insert(0, SRC)
from hydra_reposter.core.logger import setup_logger
from typing import List, Optional

app = typer.Typer()
setup_logger()  # инициализация логгера


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Hydra Reposter – модульный репостер на Telethon1.37+."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def validate(csv: str = typer.Option("data/targets.csv", help="CSV с целями")):
    """Проверка и очистка файла с юзернеймами."""
    from hydra_reposter.workers.filter import validate_csv
    validate_csv(csv)

@app.command()
def dashboard():
    from hydra_reposter.cli_dashboard import dashboard as dash_main
    dash_main()

@app.command()
def send(
    csv: str = typer.Option(..., "--csv", "-c", help="Путь к CSV с колонкой username"),
    donor: Optional[str] = typer.Option(
        None,
        "--donor",
        "-d",
        help="Ссылка или @username канала‑донора (альтернатива --chat-id)",
    ),
    chat_id: int = typer.Option(
        -1002333236978,
        "--chat-id",
        help="Числовой ID чата‑донора для случайного выбора поста",
    ),
    msg_ids: List[int] = typer.Option(
        [], "--msg-ids", "-m", help="ID сообщений (опция может повторяться)"
    ),
    sessions_dir: str = typer.Option(
        "sessions", "--sessions-dir", "-s", help="Каталог с файлами .session"
    ),
    rate: str = typer.Option(
        "slow",
        "--rate",
        help="Скорость: slow (1) или fast (3) сообщений за раз",
        show_choices=True,
        case_sensitive=False,
    ),
):
    from hydra_reposter.workers.reposter import run_reposter

    # если указан --donor, используем его; иначе числовой chat_id
    target_chat = donor if donor else chat_id

    run_reposter(
        csv=csv,
        chat_id=target_chat,
        msg_ids=msg_ids,
        sessions_dir=sessions_dir,
        rate=rate,
    )


@app.command()
def speed(rate: str = typer.Option("slow", help="slow|fast")):
    """Переключить глобальную скорость работы."""
    typer.echo(f"Скорость установлена: {rate}")


if __name__ == "__main__":
    app()
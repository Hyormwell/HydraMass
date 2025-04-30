import typer
from rich.console import Console
from rich.table import Table
from hydra_reposter.core.config import settings, set_default_delay
from hydra_reposter.utils.storage import load_quarantine, purge_expired
from hydra_reposter.utils.metrics import sent_total, current_queue

BANNER = r"""
   /\_/\
  ( o.o )   HYDRA DASHBOARD
   > ^ < 
"""

console = Console()
app = typer.Typer()

def show_banner():
    console.print(f"[green]{BANNER}[/green]")

def show_metrics():
    # TODO: здесь собираем реальные метрики
    sent = sent_total()
    queue = current_queue()
    quarantined = load_quarantine()
    table = Table(title="Метрики Hydra Reposter", show_header=True, header_style="bold cyan")
    table.add_column("Параметр")
    table.add_column("Значение", justify="right")
    table.add_row("Всего отправлено", str(sent))
    table.add_row("В очереди", str(queue))
    table.add_row("В карантине", str(len(quarantined)))
    console.print(table)

def change_delay():
    new = typer.prompt("Введите новую задержку DEFAULT_DELAY (сек)", default=str(settings.default_delay))
    try:
        val = float(new)
        set_default_delay(val)
        console.print(f"[bold green]Установлена задержка:[/bold green] {val}s")
    except ValueError:
        console.print("[red]Ошибка:[/red] введите число")

def clear_quarantine():
    purge_expired()
    console.print("[green]Карантин очищен (устаревшие записи удалены)[/green]")

@app.command()
def dashboard():
    show_banner()
    while True:
        console.print("\n[bold]Меню:[/bold]")
        console.print(" 1) Показать метрики")
        console.print(" 2) Изменить DEFAULT_DELAY")
        console.print(" 3) Очистить устаревший карантин")
        console.print(" 4) Выйти")
        choice = typer.prompt("Ваш выбор", default="4")
        if choice == "1":
            show_metrics()
        elif choice == "2":
            change_delay()
        elif choice == "3":
            clear_quarantine()
        elif choice == "4":
            console.print("[cyan]Выход...[/cyan]")
            raise typer.Exit()
        else:
            console.print("[red]Неверный выбор[/red], попробуйте ещё раз.")
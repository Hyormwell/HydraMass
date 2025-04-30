# tests/test_cli_dashboard.py
from typer.testing import CliRunner
from hydra_reposter.cli_dashboard import app

runner = CliRunner()

def test_dashboard_banner_and_exit(monkeypatch):
    # симулируем ввод "4" для выхода
    result = runner.invoke(app, input="4\n")
    assert "HYDRA DASHBOARD" in result.stdout
    assert "Выход" in result.stdout
    assert result.exit_code == 0
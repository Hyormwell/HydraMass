# tests/test_cli_args.py
from typer.testing import CliRunner
from hydra_reposter.cli import app

runner = CliRunner()

def test_send_help():
    result = runner.invoke(app, ["send", "--help"])
    assert result.exit_code == 0
    assert "--donor" in result.stdout
    assert "--msg-ids" in result.stdout
    assert "--sessions-dir" in result.stdout
    assert "--rate" in result.stdout
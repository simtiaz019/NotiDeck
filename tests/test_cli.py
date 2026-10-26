from typer.testing import CliRunner
from notideck.cli import app


def test_version_and_help():
    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert "0.1.0" in result.output
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--embedded-worker" in result.output


def test_doctor_requires_setup(tmp_path):
    result = CliRunner().invoke(app, ["doctor", "--config", str(tmp_path)])
    assert result.exit_code == 1
    assert "Setup required" in result.output

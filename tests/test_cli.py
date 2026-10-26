import pytest
from click import unstyle
from typer.testing import CliRunner
from notideck import __version__
from notideck.cli import app


@pytest.mark.parametrize("color", [False, True])
def test_version_and_help(color):
    runner = CliRunner(env={"FORCE_COLOR": "1"} if color else {"NO_COLOR": "1"})
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert unstyle(result.output).strip() == __version__
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "--embedded-worker" in unstyle(result.output)


def test_doctor_requires_setup(tmp_path):
    result = CliRunner().invoke(app, ["doctor", "--config", str(tmp_path)])
    assert result.exit_code == 1
    assert "Setup required" in result.output

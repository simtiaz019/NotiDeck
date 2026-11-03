import pytest
import logging
import os
from click import unstyle
from typer.testing import CliRunner
from notideck import __version__
from notideck.cli import app
from notideck.config import Config
from notideck.logging_config import configure_logging


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
    assert str(tmp_path / "logs" / "server.log") in result.output
    assert str(tmp_path / "logs" / "worker.log") in result.output


def test_separate_rotating_component_logs(tmp_path):
    config = Config(tmp_path)
    server = configure_logging(config, "server")
    logging.getLogger("notideck.api").info("server-probe")
    worker = configure_logging(config, "worker")
    logging.getLogger("notideck.worker").info("worker-probe")
    assert server == tmp_path / "logs" / "server.log"
    assert worker == tmp_path / "logs" / "worker.log"
    assert "server-probe" in server.read_text(encoding="utf-8")
    assert "worker-probe" in worker.read_text(encoding="utf-8")
    assert "worker-probe" not in server.read_text(encoding="utf-8")
    if os.name != "nt":
        assert server.stat().st_mode & 0o777 == 0o600
        assert worker.stat().st_mode & 0o777 == 0o600


def test_log_environment_override_must_be_absolute(tmp_path, monkeypatch):
    config = Config(tmp_path)
    monkeypatch.setenv("NOTIDECK_LOG_DIR", "relative/logs")
    with pytest.raises(ValueError, match="absolute"):
        configure_logging(config, "server")

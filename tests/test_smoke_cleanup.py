from types import SimpleNamespace
from unittest.mock import Mock
import subprocess

import pytest

from tests import wheel_smoke


def test_windows_cleanup_stops_launcher_and_children(monkeypatch):
    process = Mock(pid=1234)
    process.poll.return_value = None
    run = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(wheel_smoke, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(wheel_smoke.subprocess, "run", run)
    wheel_smoke.stop_process(process, timeout=15)
    run.assert_called_once_with(["taskkill", "/PID", "1234", "/T", "/F"], capture_output=True, timeout=15)
    process.wait.assert_called_once_with(timeout=15)
    process.terminate.assert_not_called()


def test_windows_cleanup_failure_is_not_hidden(monkeypatch):
    process = Mock(pid=1234)
    process.poll.return_value = None
    monkeypatch.setattr(wheel_smoke, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(wheel_smoke.subprocess, "run", Mock(return_value=SimpleNamespace(returncode=1)))
    with pytest.raises(RuntimeError, match="process tree"):
        wheel_smoke.stop_process(process, timeout=15)


def test_posix_cleanup_kills_unresponsive_process(monkeypatch):
    process = Mock()
    process.poll.return_value = None
    process.wait.side_effect = [subprocess.TimeoutExpired("python", 15), 0]
    monkeypatch.setattr(wheel_smoke, "os", SimpleNamespace(name="posix"))
    wheel_smoke.stop_process(process, timeout=15)
    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert process.wait.call_count == 2

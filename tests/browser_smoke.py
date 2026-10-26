"""Run real browser tests against a fresh, temporary installation."""

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="notideck-browser-") as directory:
        env = {**os.environ, "NOTIDECK_CONFIG_DIR": directory, "NOTIDECK_E2E_CONFIG": directory}
        env.pop("NOTIDECK_DATABASE_URL", None)
        with tempfile.TemporaryFile() as log:
            server = subprocess.Popen(
                [sys.executable, "-m", "notideck", "serve", "--port", "8765"], env=env, stdout=log, stderr=log
            )
            try:
                for _ in range(100):
                    if server.poll() is not None:
                        raise RuntimeError("Browser test server exited early")
                    try:
                        urllib.request.urlopen("http://127.0.0.1:8765/api/v1/health/live", timeout=1)
                        break
                    except OSError:
                        time.sleep(0.1)
                subprocess.run(
                    ["npx.cmd" if os.name == "nt" else "npx", "playwright", "test"],
                    cwd=root / "frontend",
                    env=env,
                    check=True,
                )
            finally:
                server.terminate()
                server.wait(timeout=15)


if __name__ == "__main__":
    main()

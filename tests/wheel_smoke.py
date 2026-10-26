"""Install a built wheel in a clean venv, run real API and worker subprocesses.

Uses only a temporary local HTTP receiver; no external provider credentials.
"""

import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
import venv
import tomllib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    wheel = root / "dist" / f"notideck-{version}-py3-none-any.whl"
    assert wheel.is_file(), f"Build the current version first: {wheel.name}"
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    threading.Thread(target=receiver.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix="notideck-wheel-") as directory:
        directory = Path(directory)
        venv.EnvBuilder(with_pip=True).create(directory / "venv")
        python = directory / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run([str(python), "-m", "pip", "install", "--quiet", str(wheel)], check=True)
        subprocess.run([str(python), "-m", "notideck", "--version"], check=True, cwd=directory)
        env = {
            **os.environ,
            "NOTIDECK_CONFIG_DIR": str(directory / "config"),
            "NOTIDECK_OUTBOUND_ALLOW_NETWORKS": "127.0.0.0/8",
        }
        for key in ["NOTIDECK_DATABASE_URL", "PYTHONPATH", "NOTIDECK_DATA_DIR", "NOTIDECK_SECURE_COOKIES"]:
            env.pop(key, None)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        from http.cookiejar import CookieJar

        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        csrf = ""

        def request(path, body=None, headers=None, method=None):
            req = urllib.request.Request(
                base + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json", "X-CSRF-Token": csrf, **(headers or {})},
                method=method,
            )
            with opener.open(req, timeout=10) as response:
                return json.load(response)

        with tempfile.TemporaryFile() as log:
            web = subprocess.Popen(
                [str(python), "-m", "notideck", "serve", "--port", str(port)],
                cwd=directory,
                env=env,
                stdout=log,
                stderr=log,
            )
            worker = None
            try:
                for _ in range(150):
                    try:
                        request("/api/v1/health/live")
                        break
                    except OSError:
                        if web.poll() is not None:
                            raise RuntimeError("Installed server failed to start")
                        time.sleep(0.1)
                assert b"NotiDeck" in opener.open(base).read()
                password = secrets.token_urlsafe(24) + "1!"
                token = (directory / "config/bootstrap.token").read_text().strip()
                request(
                    "/api/v1/setup",
                    {
                        "username": "admin",
                        "full_name": "Smoke Admin",
                        "email": "smoke@example.test",
                        "password": password,
                        "confirm_password": password,
                    },
                    headers={"X-Bootstrap-Token": token},
                )
                csrf = request("/api/v1/auth/login", {"username": "admin", "password": password})[
                    "csrf_token"
                ]
                channel = request(
                    "/api/v1/channels",
                    {
                        "name": "Local receiver",
                        "provider": "webhook",
                        "rate_per_minute": 60000,
                        "config": {"url": f"http://127.0.0.1:{receiver.server_port}/events"},
                    },
                )
                request("/api/v1/routes", {"name": "All events", "targets": [{"channel_id": channel["id"]}]})
                source = request("/api/v1/sources", {"name": "smoke"})
                key = request(f"/api/v1/sources/{source['id']}/keys", {})["key"]
                event = request(
                    "/api/v1/notifications",
                    {
                        "title": "Wheel smoke",
                        "message": "Real local HTTP transport",
                        "idempotency_key": "smoke-1",
                    },
                    headers={"Authorization": "Bearer " + key},
                )
                assert request("/api/v1/queue/stats")["counts"]["PENDING"] == 1
                worker = subprocess.Popen(
                    [str(python), "-m", "notideck", "worker"], cwd=directory, env=env, stdout=log, stderr=log
                )
                for _ in range(100):
                    deliveries = request("/api/v1/notifications/" + event["id"] + "/deliveries")
                    if deliveries[0]["status"] == "SENT":
                        break
                    time.sleep(0.1)
                assert deliveries[0]["status"] == "SENT", deliveries[0]["status"]
                assert deliveries[0]["attempt_history"][0]["success"]
                assert received and received[0]["title"] == "Wheel smoke"
                request("/api/v1/queue/pause", {})
                request(
                    "/api/v1/notifications",
                    {"title": "Cancel me", "message": "Queued while paused"},
                    headers={"Authorization": "Bearer " + key},
                )
                assert request("/api/v1/queue/clear", {})["affected"] == 1
                assert request("/api/v1/queue/clear", {"confirm": True})["affected"] == 1
                assert request("/api/v1/notifications")["total"] == 2
                assert request("/api/v1/health/ready")["status"] == "ready"
                print(
                    "PASS: clean wheel install, bundled UI, setup, login, channel, route, ingestion, real worker HTTP delivery, history, queue cancellation"
                )
            finally:
                if worker:
                    worker.terminate()
                    worker.wait(timeout=40)
                web.terminate()
                web.wait(timeout=15)
    receiver.shutdown()
    receiver.server_close()


if __name__ == "__main__":
    main()

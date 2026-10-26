"""Disposable Docker setup, delivery and restart test. Never uses the user's volume.

Build first: docker build -t notideck:rc-test .
Run: python tests/docker_smoke.py
The broad outbound allowlist exists only inside these disposable test containers.
"""

import json
import secrets
import subprocess
import threading
import time
import urllib.request
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wheel_smoke import free_port


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def main():
    name = "notideck-smoke-" + secrets.token_hex(6)
    volume = name + "-data"
    web = name + "-web"
    worker = name + "-worker"
    received = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
            self.send_response(202)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    receiver = ThreadingHTTPServer(("0.0.0.0", 0), Receiver)
    threading.Thread(target=receiver.serve_forever, daemon=True).start()
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    csrf = ""

    def request(path, body=None, headers=None):
        req = urllib.request.Request(
            base + path,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", "X-CSRF-Token": csrf, **(headers or {})},
        )
        with opener.open(req, timeout=10) as response:
            return json.load(response)

    def ready():
        for _ in range(100):
            try:
                request("/api/v1/health/live")
                return
            except OSError:
                time.sleep(0.2)
        raise RuntimeError("Disposable Docker web did not start")

    common = [
        "--mount",
        f"type=volume,source={volume},target=/data",
        "--add-host",
        "host.docker.internal:host-gateway",
        "-e",
        "NOTIDECK_OUTBOUND_ALLOW_NETWORKS=0.0.0.0/0,::/0",
    ]
    try:
        docker("volume", "create", volume)
        docker("run", "-d", "--name", web, "-p", f"127.0.0.1:{port}:8000", *common, "notideck:rc-test")
        ready()
        assert docker("exec", web, "id", "-u") == "10001"
        token = docker("exec", web, "cat", "/data/bootstrap.token")
        password = secrets.token_urlsafe(24) + "1!"
        request(
            "/api/v1/setup",
            {
                "username": "admin",
                "full_name": "Docker Test",
                "email": "docker@example.test",
                "password": password,
                "confirm_password": password,
            },
            headers={"X-Bootstrap-Token": token},
        )
        csrf = request("/api/v1/auth/login", {"username": "admin", "password": password})["csrf_token"]
        channel = request(
            "/api/v1/channels",
            {
                "name": "Local receiver",
                "provider": "webhook",
                "rate_per_minute": 60000,
                "config": {"url": f"http://host.docker.internal:{receiver.server_port}/events"},
            },
        )
        request("/api/v1/routes", {"name": "All", "targets": [{"channel_id": channel["id"]}]})
        source = request("/api/v1/sources", {"name": "Docker smoke"})
        key = request(f"/api/v1/sources/{source['id']}/keys", {})["key"]
        event = request(
            "/api/v1/notifications",
            {"title": "Docker smoke", "message": "Persistent queue", "idempotency_key": "docker-1"},
            headers={"Authorization": "Bearer " + key},
        )
        docker("restart", web)
        ready()
        csrf = request("/api/v1/auth/login", {"username": "admin", "password": password})["csrf_token"]
        assert request("/api/v1/queue/stats")["counts"]["PENDING"] == 1
        docker("run", "-d", "--name", worker, *common, "notideck:rc-test", "worker")
        for _ in range(150):
            deliveries = request("/api/v1/notifications/" + event["id"] + "/deliveries")
            if deliveries[0]["status"] == "SENT":
                break
            time.sleep(0.2)
        assert deliveries[0]["status"] == "SENT", deliveries[0]["status"]
        assert deliveries[0]["attempt_history"][0]["success"]
        assert received[0]["title"] == "Docker smoke"
        docker("stop", "--time", "45", worker)
        assert not any(w["healthy"] for w in request("/api/v1/queue/stats")["workers"])
        assert request("/api/v1/health/ready")["status"] == "ready"
        print(
            "PASS: non-root Docker, setup, persistent queued event after restart, real HTTP delivery, history, graceful worker shutdown"
        )
    finally:
        for container in [worker, web]:
            subprocess.run(
                ["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        subprocess.run(["docker", "volume", "rm", volume], stdout=subprocess.DEVNULL, check=True)
        receiver.shutdown()
        receiver.server_close()


if __name__ == "__main__":
    main()

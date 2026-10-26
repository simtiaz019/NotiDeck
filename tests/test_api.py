import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest

import notideck.security as security

from sqlalchemy import select

from notideck.database.models import APIKey, Channel, Session, User
from tests.conftest import initialize, send


@pytest.fixture
def rate_clock(monkeypatch):
    # Replace only the limiter's clock; session expiry and request timing stay real.
    clock = SimpleNamespace(now=60_059.999)
    monkeypatch.setattr(security, "time", SimpleNamespace(time=lambda: clock.now))
    return clock


def test_bootstrap_protected_and_restart_safe(raw_client, config):
    assert raw_client.get("/api/v1/setup/status").json()["initialized"] is False
    assert raw_client.post("/api/v1/setup/test", json={}).status_code == 403
    assert initialize(raw_client, config).status_code == 200
    assert initialize(raw_client, config).status_code == 409
    assert raw_client.get("/api/v1/health/ready").status_code == 200
    from fastapi.testclient import TestClient
    from notideck.api import create_app

    other = create_app(config)
    with TestClient(other) as restarted:
        assert restarted.get("/api/v1/setup/status").json()["initialized"] is True
        assert initialize(restarted, config).status_code == 409
    other.state.engine.dispose()


def test_authentication_csrf_and_secrets(client, app, scenario):
    assert (
        client.post("/api/v1/sources", json={"name": "no-csrf"}, headers={"X-CSRF-Token": ""}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"username": "admin", "password": "bad"},
            headers={"Origin": "https://evil.test"},
        ).status_code
        == 403
    )
    channel = client.get("/api/v1/channels/" + scenario["channel"]["id"]).json()
    assert "credentials" not in channel
    with app.state.factory() as db:
        user = db.scalar(select(User))
        assert user.password_hash.startswith("$argon2id$")
        key = db.scalar(select(APIKey))
        assert scenario["key"] not in key.token_hash
        stored = db.get(Channel, scenario["channel"]["id"])
        assert "example.com" not in stored.credentials
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/notifications").status_code == 401


def test_viewer_permissions(client):
    response = client.post(
        "/api/v1/users",
        json={
            "username": "viewer",
            "full_name": "Viewer",
            "email": "v@example.test",
            "password": "viewer password 123",
            "role": "VIEWER",
        },
    )
    assert response.status_code == 201, response.text
    result = client.post("/api/v1/auth/login", json={"username": "viewer", "password": "viewer password 123"})
    client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    assert client.get("/api/v1/notifications").status_code == 200
    assert client.get("/api/v1/users").status_code == 403
    assert (
        client.post(
            "/api/v1/channels",
            json={"name": "test", "provider": "webhook", "config": {"url": "https://example.com"}},
        ).status_code
        == 403
    )
    assert client.post("/api/v1/queue/clear", json={"confirm": True}).status_code == 403


def test_idempotency_and_scoped_keys(client, scenario):
    first = send(client, scenario, idempotency_key="one")
    assert first.status_code == 202, first.text
    second = send(client, scenario, idempotency_key="one")
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["replayed"] is True
    assert client.get("/api/v1/queue").json()["total"] == 1
    assert send(client, scenario, idempotency_key="one", message="different").status_code == 409
    assert send(client, scenario, source="another").status_code == 403
    assert client.post("/api/v1/notifications", json={"title": "x", "message": "y"}).status_code == 401
    key_id = client.get(f"/api/v1/sources/{scenario['source']['id']}/keys").json()[0]["id"]
    client.post("/api/v1/keys/" + key_id + "/revoke")
    assert send(client, scenario).status_code == 401


def test_queue_preview_cancel_preserves_history(client, scenario):
    event = send(client, scenario).json()
    preview = client.post("/api/v1/queue/clear", json={}).json()
    assert preview["affected"] == 1 and preview["preview"]
    assert client.get("/api/v1/queue").json()["items"][0]["status"] == "PENDING"
    response = client.post("/api/v1/queue/clear", json={"confirm": True, "reason": "maintenance"})
    assert response.json()["affected"] == 1
    assert client.get("/api/v1/notifications/" + event["id"]).json()["status"] == "CANCELLED"
    assert client.get("/api/v1/queue").json()["items"][0]["status"] == "CANCELLED"
    assert any(a["operation"] == "queue.clear" for a in client.get("/api/v1/audits").json()["items"])


def test_signed_webhook(client, scenario):
    source_id = scenario["source"]["id"]
    secret = client.post(f"/api/v1/sources/{source_id}/webhook-secret").json()["secret"]
    timestamp = str(int(time.time()))
    body = json.dumps(
        {"title": "Signed event", "message": "Authenticated", "idempotency_key": "signed-1"}
    ).encode()
    signature = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers = {
        "X-NotiDeck-Timestamp": timestamp,
        "X-NotiDeck-Signature": signature,
        "Content-Type": "application/json",
    }
    response = client.post("/api/v1/webhooks/" + source_id, content=body, headers=headers)
    assert response.status_code == 202, response.text
    assert client.post("/api/v1/webhooks/" + source_id, content=body, headers=headers).json()["replayed"]
    headers["X-NotiDeck-Timestamp"] = "1"
    assert client.post("/api/v1/webhooks/" + source_id, content=body, headers=headers).status_code == 401


def test_request_limits_and_validation_redaction(client):
    assert client.post("/api/v1/auth/login", content=b"x" * 262145).status_code == 413
    response = client.post("/api/v1/auth/login", json={"username": 123, "password": "DO-NOT-ECHO"})
    assert response.status_code == 422
    assert "DO-NOT-ECHO" not in response.text
    assert client.get("/api/v1/health/live").headers["X-Content-Type-Options"] == "nosniff"


def test_sessions_expire_and_password_changes_revoke(client, app):
    response = client.post(
        "/api/v1/auth/password",
        json={"current_password": "correct horse 123!", "password": "a different password 321"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
    result = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "a different password 321"}
    )
    assert result.status_code == 200
    with app.state.factory() as db:
        session = db.scalar(select(Session))
        session.expires_at = time.time() - 1
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_source_disable_and_rate_limit(client, scenario, rate_clock):
    source = scenario["source"]
    value = {
        k: source[k]
        for k in ["name", "description", "environment", "enabled", "rate_limit", "networks", "tags"]
    }
    value["rate_limit"] = 1
    assert client.patch("/api/v1/sources/" + source["id"], json=value).status_code == 200
    assert send(client, scenario).status_code == 202
    assert send(client, scenario).status_code == 429
    # The first request in the next fixed minute is accepted, then limited again.
    rate_clock.now = 60_060.0
    assert send(client, scenario).status_code == 202
    assert send(client, scenario).status_code == 429
    value["enabled"] = False
    client.patch("/api/v1/sources/" + source["id"], json=value)
    assert send(client, scenario).status_code == 403


def test_expired_and_empty_scope_keys(client, scenario):
    source_id = scenario["source"]["id"]
    key = client.post(f"/api/v1/sources/{source_id}/keys", json={"scopes": []}).json()["key"]
    assert send(client, {**scenario, "key": key}).status_code == 403
    assert (
        client.post(f"/api/v1/sources/{source_id}/keys", json={"expires_at": time.time() - 1}).status_code
        == 422
    )


def test_operator_cannot_cancel_but_can_pause(client, scenario):
    user = client.post(
        "/api/v1/users",
        json={
            "username": "operator",
            "full_name": "Operator",
            "email": "op@example.test",
            "password": "operator-test-123",
            "role": "OPERATOR",
        },
    )
    assert user.status_code == 201
    login = client.post("/api/v1/auth/login", json={"username": "operator", "password": "operator-test-123"})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.post("/api/v1/queue/pause", json={}).status_code == 200
    assert client.post("/api/v1/queue/clear", json={"confirm": True}).status_code == 403
    assert client.post("/api/v1/sources", json={"name": "forbidden"}).status_code == 403


def test_duplicate_credentials_and_safe_delete(client, scenario, app, config):
    original = scenario["channel"]["id"]
    duplicate = client.post("/api/v1/channels/" + original + "/duplicate").json()
    assert duplicate["enabled"] is False
    with app.state.factory() as db:
        assert config.decrypt(db.get(Channel, duplicate["id"]).credentials) == config.decrypt(
            db.get(Channel, original).credentials
        )
    assert client.delete("/api/v1/channels/" + original).status_code == 409
    assert client.delete("/api/v1/channels/" + duplicate["id"]).status_code == 200


def test_network_allowlist_and_default_source_environment(client, scenario):
    source = scenario["source"]
    value = {
        k: source[k]
        for k in ["name", "description", "environment", "enabled", "rate_limit", "networks", "tags"]
    }
    value["environment"] = "staging"
    client.patch("/api/v1/sources/" + source["id"], json=value)
    response = client.post(
        "/api/v1/notifications",
        json={"title": "Default environment", "message": "From source"},
        headers={"Authorization": "Bearer " + scenario["key"]},
    )
    assert response.status_code == 202
    assert client.get("/api/v1/notifications/" + response.json()["id"]).json()["environment"] == "staging"
    value["networks"] = ["10.0.0.0/8"]
    client.patch("/api/v1/sources/" + source["id"], json=value)
    assert send(client, scenario).status_code == 403


def test_login_rate_limit(raw_client, config, rate_clock):
    assert initialize(raw_client, config).status_code == 200
    for _ in range(10):
        assert (
            raw_client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code
            == 401
        )
    assert (
        raw_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "correct horse 123!"}
        ).status_code
        == 429
    )

    rate_clock.now += 300
    assert (
        raw_client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "correct horse 123!"}
        ).status_code
        == 200
    )


def test_offline_api_docs_and_examples(client):
    assert "/api-docs/swagger-ui-bundle.js" in client.get("/api/docs").text
    assert client.get("/api/openapi.json").json()["components"]["schemas"]["EventInput"]["examples"]


def test_retention_preserves_active_events_and_audits(client, scenario, app):
    from sqlalchemy import update
    from notideck.database.models import Notification

    cancelled = send(client, scenario, idempotency_key="old-cancelled").json()
    client.post("/api/v1/queue/clear", json={"confirm": True})
    active = send(client, scenario, idempotency_key="old-active").json()
    with app.state.factory() as db:
        db.execute(update(Notification).values(created_at=time.time() - 100 * 86400))
        db.commit()
    before = client.get("/api/v1/audits").json()["total"]
    assert client.post("/api/v1/retention", json={}).json()["affected"] == 1
    assert client.post("/api/v1/retention", json={"confirm": True}).json()["affected"] == 1
    assert client.get("/api/v1/notifications/" + cancelled["id"]).status_code == 404
    assert client.get("/api/v1/notifications/" + active["id"]).status_code == 200
    assert client.get("/api/v1/audits").json()["total"] == before + 1


def test_bootstrap_verified_before_database_configuration(raw_client, config):
    token = config.token_path.read_text().strip()
    assert raw_client.post("/api/v1/setup/verify", json={}).status_code == 403
    assert (
        raw_client.post(
            "/api/v1/setup/verify", json={}, headers={"X-Bootstrap-Token": "wrong-token"}
        ).status_code
        == 403
    )
    result = raw_client.post(
        "/api/v1/setup/verify", json={}, headers={"X-Bootstrap-Token": "  " + token + "  "}
    )
    assert result.status_code == 200 and result.json() == {"verified": True}
    assert token not in result.text
    assert not config.database_url
    assert initialize(raw_client, config).status_code == 200
    assert (
        raw_client.post("/api/v1/setup/verify", json={}, headers={"X-Bootstrap-Token": token}).status_code
        == 409
    )


def test_bootstrap_non_ascii_token_is_rejected(raw_client):
    response = raw_client.post(
        "/api/v1/setup/verify", json={}, headers={b"X-Bootstrap-Token": b"wrong-\xc2\xa0-token"}
    )
    assert response.status_code == 403

import pytest
from fastapi.testclient import TestClient
from notideck.api import create_app
from notideck.config import Config


@pytest.fixture
def config(tmp_path):
    return Config(tmp_path)


@pytest.fixture
def app(config):
    return create_app(config)


@pytest.fixture
def raw_client(app):
    with TestClient(app) as client:
        yield client
    if app.state.engine:
        app.state.engine.dispose()


def initialize(client, config):
    return client.post(
        "/api/v1/setup",
        json={
            "username": "admin",
            "full_name": "Test Admin",
            "email": "admin@example.test",
            "password": "correct horse 123!",
            "confirm_password": "correct horse 123!",
        },
        headers={"X-Bootstrap-Token": config.token_path.read_text()},
    )


@pytest.fixture
def client(raw_client, config):
    result = initialize(raw_client, config)
    assert result.status_code == 200, result.text
    result = raw_client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "correct horse 123!"}
    )
    assert result.status_code == 200, result.text
    raw_client.headers["X-CSRF-Token"] = result.json()["csrf_token"]
    return raw_client


@pytest.fixture
def scenario(client):
    channel = client.post(
        "/api/v1/channels",
        json={
            "name": "Operations webhook",
            "provider": "webhook",
            "rate_per_minute": 60000,
            "config": {"url": "https://example.com/events"},
        },
    )
    assert channel.status_code == 201, channel.text
    channel = channel.json()
    rule = client.post(
        "/api/v1/routes",
        json={
            "name": "Production alerts",
            "conditions": [{"field": "environment", "op": "equals", "value": "production"}],
            "targets": [{"channel_id": channel["id"]}],
        },
    )
    assert rule.status_code == 201, rule.text
    source = client.post("/api/v1/sources", json={"name": "database", "environment": "production"}).json()
    key = client.post(f"/api/v1/sources/{source['id']}/keys", json={}).json()["key"]
    return {"channel": channel, "source": source, "key": key, "rule": rule.json()}


def send(client, scenario, **changes):
    body = {
        "title": "Replication lag",
        "message": "Lag above threshold",
        "severity": "CRITICAL",
        "environment": "production",
        **changes,
    }
    return client.post(
        "/api/v1/notifications", json=body, headers={"Authorization": "Bearer " + scenario["key"]}
    )

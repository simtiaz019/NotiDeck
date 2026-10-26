import time

from sqlalchemy import select, update

from notideck.database.models import Audit, Delivery, Notification, RateBucket, Session, Worker
from notideck.maintenance import housekeeping
from notideck.providers import Result
from notideck.worker import process_one
from tests.conftest import send
from tests.test_worker import FakeProvider


def test_retention_opt_in_and_active_jobs(client, scenario, app, config):
    completed = send(client, scenario).json()["id"]
    process_one(app.state.factory, config, {"webhook": FakeProvider(Result(True))})
    active = send(client, scenario, title="Still pending").json()["id"]
    with app.state.factory() as db:
        db.execute(update(Notification).values(created_at=time.time() - 100 * 86400))
        # Even inconsistent terminal aggregates must not delete an active delivery.
        db.get(Notification, active).status = "FAILED"
        db.add(Worker(id="obsolete", heartbeat=0))
        db.commit()
    assert client.get("/api/v1/settings").json()["retention_enabled"] is False
    housekeeping(app.state.factory)
    with app.state.factory() as db:
        assert db.get(Notification, completed)
        assert db.get(Worker, "obsolete") is None
        assert db.scalar(select(Session))  # Valid login session survives cleanup.
        db.delete(db.get(RateBucket, "maintenance"))
        db.commit()
    assert client.patch("/api/v1/settings", json={"retention_enabled": True}).status_code == 200
    housekeeping(app.state.factory)
    with app.state.factory() as db:
        assert db.get(Notification, completed) is None
        assert db.get(Notification, active)
        assert db.scalar(select(Delivery).where(Delivery.notification_id == active))
        assert db.scalar(select(Audit).where(Audit.operation == "retention.deleted"))


def test_queue_action_respects_visible_status(client, scenario, app):
    first = send(client, scenario).json()["id"]
    send(client, scenario, title="Keep pending")
    with app.state.factory() as db:
        db.execute(update(Delivery).where(Delivery.notification_id == first).values(status="RETRY_SCHEDULED"))
        db.commit()
    body = {"status": "RETRY_SCHEDULED"}
    assert client.post("/api/v1/queue/clear", json=body).json()["affected"] == 1
    assert client.post("/api/v1/queue/clear", json={**body, "confirm": True}).json()["affected"] == 1
    assert client.get("/api/v1/queue?status=PENDING").json()["total"] == 1


def test_invalid_admin_inputs_are_client_errors(client):
    for payload in [{"timezone": "No/SuchZone"}, {"max_attempts": True}, {"retention_enabled": "yes"}]:
        assert client.patch("/api/v1/settings", json=payload).status_code == 422
    assert (
        client.post("/api/v1/auth/password", json={"current_password": {}, "password": []}).status_code == 422
    )
    for template in ["{{ missing }}", "{{"]:
        response = client.post(
            "/api/v1/templates/preview",
            json={"template": template, "event": {"title": "Test", "message": "Test"}},
        )
        assert response.status_code == 422

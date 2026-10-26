import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select, update

from notideck.database.models import Attempt, Channel, Delivery
from notideck.providers import Result
from notideck.worker import backoff, claim, process_one
from tests.conftest import send


class FakeProvider:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def send(self, *args):
        self.calls += 1
        return self.result


def test_worker_records_acceptance(client, scenario, app, config):
    event = send(client, scenario).json()
    provider = FakeProvider(Result(True, message_id="provider-1"))
    assert process_one(app.state.factory, config, {"webhook": provider})
    assert provider.calls == 1
    result = client.get("/api/v1/notifications/" + event["id"] + "/deliveries").json()[0]
    assert result["status"] == "SENT"
    assert result["provider_message_id"] == "provider-1"
    assert result["attempt_history"][0]["success"]
    assert not process_one(app.state.factory, config, {"webhook": provider})


def test_retry_dead_letter_and_manual_retry(client, scenario, app, config):
    send(client, scenario)
    client.patch("/api/v1/settings", json={"max_attempts": 2})
    provider = FakeProvider(Result(False, True, code="429", error="Rate limited", retry_after=20))
    assert process_one(app.state.factory, config, {"webhook": provider})
    with app.state.factory() as db:
        job = db.scalar(select(Delivery))
        assert job.status == "RETRY_SCHEDULED"
        assert job.available_at >= time.time() + 18
        db.execute(update(Delivery).values(available_at=0))
        db.execute(update(Channel).values(next_send_at=0))
        db.commit()
    process_one(app.state.factory, config, {"webhook": provider})
    assert client.get("/api/v1/queue").json()["items"][0]["status"] == "DEAD_LETTER"
    assert client.post("/api/v1/queue/retry", json={"confirm": True}).json()["affected"] == 1
    assert client.get("/api/v1/queue").json()["items"][0]["status"] == "PENDING"


def test_lease_recovery_and_racing_claims(client, scenario, app):
    send(client, scenario)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda n: claim(app.state.factory, str(n)), range(4)))
    assert len([r for r in results if r]) == 1
    job_id, token = next(r for r in results if r)
    assert client.post("/api/v1/queue/clear", json={"confirm": True}).json()["affected"] == 0
    with app.state.factory() as db:
        db.execute(update(Delivery).where(Delivery.id == job_id).values(lease_until=time.time() - 1))
        db.execute(update(Channel).values(next_send_at=0))
        db.commit()
    reclaimed = claim(app.state.factory, "new")
    assert reclaimed[0] == job_id and reclaimed[1] != token


def test_pause_and_backoff(client, scenario, app):
    send(client, scenario)
    client.post("/api/v1/queue/pause", json={})
    assert claim(app.state.factory, "worker") is None
    client.post("/api/v1/queue/resume", json={})
    assert claim(app.state.factory, "worker")
    assert 7.5 <= backoff(1) <= 12.5
    assert backoff(1, retry_after=120) >= 120


def test_nonretryable_failure(client, scenario, app, config):
    send(client, scenario)
    process_one(
        app.state.factory, config, {"webhook": FakeProvider(Result(False, error="Invalid destination"))}
    )
    with app.state.factory() as db:
        assert db.scalar(select(Delivery)).status == "FAILED"
        assert db.scalar(select(Attempt)).retryable is False


def test_stale_worker_cannot_finish_new_lease(client, scenario, app, config):
    send(client, scenario)

    class LostLease:
        def send(self, *args):
            with app.state.factory() as db:
                db.execute(update(Delivery).values(lease_token="replacement-lease"))
                db.commit()
            return Result(True)

    process_one(app.state.factory, config, {"webhook": LostLease()})
    with app.state.factory() as db:
        assert db.scalar(select(Delivery)).status == "IN_PROGRESS"
        assert db.scalar(select(Attempt)) is None


def test_concurrent_idempotent_ingestion(client, scenario, app):
    from notideck.database.models import Source
    from notideck.schemas import EventInput
    from notideck.services import ingest

    def submit(_):
        with app.state.factory() as db:
            source = db.get(Source, scenario["source"]["id"])
            return ingest(
                db, source, EventInput(title="Concurrent", message="Same event", idempotency_key="racing")
            )[0].id

    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(submit, range(4)))
    assert len(set(ids)) == 1
    assert client.get("/api/v1/queue").json()["total"] == 1


def test_lease_renewal_keeps_slow_delivery_owned(client, scenario, app, config, monkeypatch):
    import notideck.worker as worker

    monkeypatch.setattr(worker, "LEASE_SECONDS", 0.6)
    send(client, scenario)

    class Slow:
        def send(self, *args):
            time.sleep(1)
            assert claim(app.state.factory, "competing-worker") is None
            return Result(True)

    assert process_one(app.state.factory, config, {"webhook": Slow()})
    with app.state.factory() as db:
        assert db.scalar(select(Delivery)).status == "SENT"


def test_expired_lease_cannot_be_renewed(client, scenario, app):
    from notideck.worker import renew_lease

    send(client, scenario)
    job_id, token = claim(app.state.factory, "first")
    with app.state.factory() as db:
        db.execute(update(Delivery).where(Delivery.id == job_id).values(lease_until=time.time() - 1))
        db.commit()
    assert not renew_lease(app.state.factory, job_id, token, "first")


def test_bad_credentials_record_terminal_failure(client, scenario, app, config):
    send(client, scenario)
    with app.state.factory() as db:
        db.get(Channel, scenario["channel"]["id"]).credentials = "invalid-ciphertext"
        db.commit()
    assert process_one(app.state.factory, config, {"webhook": FakeProvider(Result(True))})
    with app.state.factory() as db:
        assert db.scalar(select(Delivery)).status == "FAILED"
        assert "cannot be decrypted" in db.scalar(select(Attempt)).error

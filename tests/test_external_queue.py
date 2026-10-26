"""Optional external DB queue integration; requires a dedicated disposable DB."""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import delete, select, update

from notideck.database import engine_for, migrate, sessions
from notideck.database.models import Attempt, Channel, Delivery, Notification, Rule, Source
from notideck.schemas import EventInput
from notideck.services import ingest
from notideck.worker import claim, process_one
from notideck.providers import Result


@pytest.mark.skipif(
    not os.getenv("NOTIDECK_TEST_DATABASE_URL"), reason="Live external database not configured"
)
def test_external_claim_race_and_idempotency(config):
    engine = engine_for(os.environ["NOTIDECK_TEST_DATABASE_URL"])
    migrate(engine)
    factory = sessions(engine)
    suffix = str(uuid.uuid4())
    with factory() as db:
        source = Source(name="external-" + suffix)
        channel = Channel(
            name="external", provider="webhook", credentials=config.encrypt("{}"), rate_per_minute=60000
        )
        db.add_all([source, channel])
        db.flush()
        rule = Rule(
            name="external-" + suffix,
            conditions=[{"field": "environment", "op": "equals", "value": suffix}],
            targets=[{"channel_id": channel.id}],
        )
        db.add(rule)
        db.commit()
        source_id, channel_id, rule_id = source.id, channel.id, rule.id
    try:

        def receive(_):
            with factory() as db:
                return ingest(
                    db,
                    db.get(Source, source_id),
                    EventInput(
                        title="External test",
                        message="Concurrent • বাংলা",
                        environment=suffix,
                        idempotency_key=suffix,
                    ),
                )[0].id

        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(receive, range(4)))
        assert len(set(ids)) == 1
        with ThreadPoolExecutor(max_workers=4) as pool:
            claims = list(pool.map(lambda n: claim(factory, str(n)), range(4)))
        assert len([c for c in claims if c]) == 1
        with factory() as db:
            assert (
                db.scalar(select(Delivery).where(Delivery.notification_id == ids[0])).status == "IN_PROGRESS"
            )
            db.execute(
                update(Delivery).where(Delivery.notification_id == ids[0]).values(lease_until=time.time() - 1)
            )
            db.execute(update(Channel).where(Channel.id == channel_id).values(next_send_at=0))
            db.commit()
        assert claim(factory, "recovery")
        timestamp = time.time() + 0.123456
        with factory() as db:
            job = db.scalar(select(Delivery).where(Delivery.notification_id == ids[0]))
            job.available_at = timestamp
            job.status = "PENDING"
            job.lease_token = None
            job.lease_until = None
            db.commit()
        with factory() as db:
            job = db.scalar(select(Delivery).where(Delivery.notification_id == ids[0]))
            assert abs(job.available_at - timestamp) < 0.00001
            assert db.get(Notification, ids[0]).message == "Concurrent • বাংলা"
            job.available_at = 0
            db.get(Channel, channel_id).next_send_at = 0
            db.commit()

        class Provider:
            def send(self, *args):
                return Result(True, message_id="external-accepted")

        assert process_one(factory, config, {"webhook": Provider()})
        with factory() as db:
            job = db.scalar(select(Delivery).where(Delivery.notification_id == ids[0]))
            assert job.status == "SENT"
            assert db.get(Notification, ids[0]).status == "SENT"
            assert db.scalar(select(Attempt).where(Attempt.delivery_id == job.id)).success

    finally:
        with factory() as db:
            events = select(Notification.id).where(Notification.source_id == source_id)
            jobs = select(Delivery.id).where(Delivery.notification_id.in_(events))
            db.execute(delete(Attempt).where(Attempt.delivery_id.in_(jobs)))
            db.execute(delete(Delivery).where(Delivery.notification_id.in_(events)))
            db.execute(delete(Notification).where(Notification.source_id == source_id))
            db.execute(delete(Rule).where(Rule.id == rule_id))
            db.execute(delete(Channel).where(Channel.id == channel_id))
            db.execute(delete(Source).where(Source.id == source_id))
            db.commit()
        engine.dispose()

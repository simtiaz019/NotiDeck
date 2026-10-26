"""Database-backed claims, fenced completion and bounded provider calls.

At-least-once: a crash after provider acceptance can cause another send.
"""

import json
import logging
import random
import signal
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from cryptography.fernet import InvalidToken

from sqlalchemy import func, select, update

from notideck.database import engine_for, schema_current, sessions
from notideck.database.models import Attempt, Channel, Delivery, Worker
from notideck.providers import Result, registry
from notideck.services import settings, update_aggregate

log = logging.getLogger("notideck.worker")
READY = ["PENDING", "RETRY_SCHEDULED"]
LEASE_SECONDS = 180


def backoff(attempt: int, base: int = 10, retry_after: float | None = None):
    return max(min(3600, base * 2 ** min(attempt - 1, 12)) * random.uniform(0.75, 1.25), retry_after or 0)


def claim(factory, worker_id):
    now = time.time()
    with factory() as db:
        if settings(db).get("dispatch_paused", False):
            return None
        # Recovery is part of normal polling, not just process startup.
        db.execute(
            update(Delivery)
            .where(Delivery.status == "IN_PROGRESS", Delivery.lease_until < now)
            .values(status="RETRY_SCHEDULED", lease_token=None, lease_until=None, available_at=now)
        )
        query = (
            select(Delivery)
            .join(Channel)
            .where(
                Delivery.status.in_(READY),
                Delivery.available_at <= now,
                Channel.enabled.is_(True),
                Channel.paused.is_(False),
                Channel.next_send_at <= now,
            )
            .order_by(Delivery.priority, Delivery.available_at, Delivery.id)
            .limit(1)
        )
        dialect = db.bind.dialect.name
        if dialect in {"postgresql", "mysql"}:
            query = query.with_for_update(skip_locked=True, of=Delivery)
        # Oracle and SQLite use the same portable conditional claim (no FETCH FIRST + FOR UPDATE).
        job = db.scalar(query)
        if not job:
            db.commit()
            return None
        token = str(uuid.uuid4())
        result = db.execute(
            update(Delivery)
            .where(Delivery.id == job.id, Delivery.status.in_(READY))
            .values(status="IN_PROGRESS", lease_token=token, lease_until=now + LEASE_SECONDS, updated_at=now),
            execution_options={"synchronize_session": False},
        )
        if not result.rowcount:
            db.rollback()
            return None
        channel = db.get(Channel, job.channel_id)
        reserved = db.execute(
            update(Channel)
            .where(
                Channel.id == channel.id,
                Channel.next_send_at <= now,
                Channel.paused.is_(False),
                Channel.enabled.is_(True),
            )
            .values(next_send_at=now + 60 / channel.rate_per_minute)
        )
        if not reserved.rowcount:
            db.rollback()
            return None
        db.commit()
        return job.id, token


def renew_lease(factory, job_id, token, worker_id):
    now = time.time()
    with factory() as db:
        result = db.execute(
            update(Delivery)
            .where(
                Delivery.id == job_id,
                Delivery.status == "IN_PROGRESS",
                Delivery.lease_token == token,
                Delivery.lease_until > now,
            )
            .values(lease_until=now + LEASE_SECONDS)
        )
        if result.rowcount:
            db.execute(update(Worker).where(Worker.id == worker_id).values(heartbeat=now))
        db.commit()
        return bool(result.rowcount)


@contextmanager
def keep_lease(factory, job_id, token, worker_id):
    finished = threading.Event()
    lost = threading.Event()

    def heartbeat():
        while not finished.wait(max(0.05, min(30, LEASE_SECONDS / 3))):
            try:
                if not renew_lease(factory, job_id, token, worker_id):
                    lost.set()
                    break
            except Exception:
                # Transient DB failure may recover before expiry; never emit connection secrets.
                log.warning(json.dumps({"event": "lease_renewal_failed", "delivery_id": job_id}))

    thread = threading.Thread(target=heartbeat, name="notideck-lease", daemon=True)
    thread.start()
    try:
        yield lost
    finally:
        finished.set()
        thread.join(timeout=5)


def process_one(factory, config, providers, worker_id="local"):
    claimed = claim(factory, worker_id)
    if not claimed:
        return False
    job_id, token = claimed
    start = time.monotonic()
    with keep_lease(factory, job_id, token, worker_id) as lost:
        try:
            with factory() as db:
                job = db.get(Delivery, job_id)
                channel = db.get(Channel, job.channel_id)
                provider = providers.get(channel.provider)
                credentials = json.loads(config.decrypt(channel.credentials))
                rendered, recipient = job.rendered, job.recipient
            result = (
                provider.send(credentials, rendered, recipient)
                if provider
                else Result(False, error="Provider not installed")
            )
        except (InvalidToken, json.JSONDecodeError):
            result = Result(
                False,
                error="Channel credentials cannot be decrypted; verify the master key or re-save the channel",
            )
        except Exception:
            # Do not log exception strings: SDK errors may contain credentials.
            result = Result(False, True, error="Provider failed unexpectedly")
        if lost.is_set():
            log.warning(json.dumps({"event": "delivery_lease_lost", "delivery_id": job_id}))
            return True
    duration = (time.monotonic() - start) * 1000
    with factory() as db:
        # Lock/fence first; an expired worker must not overwrite a reclaimed job.
        owns = db.execute(
            update(Delivery)
            .where(
                Delivery.id == job_id,
                Delivery.status == "IN_PROGRESS",
                Delivery.lease_token == token,
                Delivery.lease_until > time.time(),
            )
            .values(updated_at=time.time())
        )
        if not owns.rowcount:
            db.rollback()
            return True
        job = db.get(Delivery, job_id)
        job.attempts += 1
        options = settings(db)
        number = (db.scalar(select(func.max(Attempt.number)).where(Attempt.delivery_id == job.id)) or 0) + 1
        db.add(
            Attempt(
                delivery_id=job.id,
                number=number,
                success=result.success,
                retryable=result.retryable,
                code=result.code,
                error=result.error,
                duration_ms=duration,
            )
        )
        if result.success:
            job.status = "SENT"
            job.provider_message_id = result.message_id
            job.accepted_at = result.accepted_at or time.time()
        elif result.retryable and job.attempts < options.get("max_attempts", 5):
            job.status = "RETRY_SCHEDULED"
            job.available_at = time.time() + backoff(
                job.attempts, options.get("retry_base", 10), result.retry_after
            )
        else:
            job.status = "DEAD_LETTER" if result.retryable else "FAILED"
        if result.retry_after:
            db.execute(
                update(Channel)
                .where(Channel.id == job.channel_id, Channel.next_send_at < time.time() + result.retry_after)
                .values(next_send_at=time.time() + result.retry_after)
            )
        job.lease_token = None
        job.lease_until = None
        update_aggregate(db, job.notification_id)
        db.commit()
        log.info(
            json.dumps(
                {
                    "event": "delivery_attempt",
                    "delivery_id": job.id,
                    "status": job.status,
                    "duration_ms": round(duration, 1),
                }
            )
        )
    return True


def run(config, concurrency=1, stop=None):
    if not config.database_url:
        raise RuntimeError("Complete setup before starting a worker")
    engine = engine_for(config.database_url)
    if not schema_current(engine):
        raise RuntimeError("Database migration required")
    if engine.dialect.name == "sqlite" and concurrency != 1:
        raise ValueError("SQLite supports one worker thread; use PostgreSQL/MySQL for concurrency")
    stop = stop or threading.Event()
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *_: stop.set())
    factory, providers = sessions(engine), registry()
    worker_id = str(uuid.uuid4())
    with factory() as db:
        db.add(Worker(id=worker_id, heartbeat=time.time(), processed=0))
        db.commit()

    def loop(index):
        next_maintenance = 0.0
        while not stop.is_set():
            try:
                if index == 0 and time.monotonic() >= next_maintenance:
                    from notideck.maintenance import housekeeping

                    housekeeping(factory)
                    next_maintenance = time.monotonic() + 60
                processed = process_one(factory, config, providers, worker_id)
                with factory() as db:
                    db.execute(
                        update(Worker)
                        .where(Worker.id == worker_id)
                        .values(heartbeat=time.time(), processed=Worker.processed + int(processed))
                    )
                    db.commit()
                if not processed:
                    stop.wait(1)
            except Exception:
                log.error(json.dumps({"event": "worker_iteration_failed", "worker_id": worker_id}))
                stop.wait(3)

    try:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            list(executor.map(loop, range(concurrency)))
    finally:
        with factory() as db:
            db.execute(update(Worker).where(Worker.id == worker_id).values(heartbeat=0))
            db.commit()
        engine.dispose()

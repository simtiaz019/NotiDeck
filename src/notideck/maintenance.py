"""Bounded maintenance. Audit history is never part of notification retention."""

import time

from sqlalchemy import delete, func, or_, select, update

from notideck.database.models import Attempt, Delivery, Notification, RateBucket, Session, Worker
from notideck.services import audit, settings

TERMINAL = ["SENT", "FAILED", "CANCELLED", "PARTIAL", "UNROUTED"]
ACTIVE = ["PENDING", "IN_PROGRESS", "RETRY_SCHEDULED"]


def retain_notifications(db, actor, confirm=False, limit=500):
    cutoff = time.time() - settings(db).get("retention_days", 90) * 86400
    ids = list(
        db.scalars(
            select(Notification.id)
            .where(Notification.created_at < cutoff, Notification.status.in_(TERMINAL))
            .order_by(Notification.created_at, Notification.id)
            .limit(limit)
        )
    )
    if not confirm:
        return {"affected": len(ids), "preview": True, "batch_limit": limit}
    affected = 0
    for id in ids:
        claimed = db.execute(
            update(Notification)
            .where(Notification.id == id, Notification.status.in_(TERMINAL))
            .values(updated_at=time.time())
        )
        if not claimed.rowcount:
            continue
        active = db.scalar(
            select(func.count())
            .select_from(Delivery)
            .where(Delivery.notification_id == id, Delivery.status.in_(ACTIVE))
        )
        if active:
            continue
        jobs = select(Delivery.id).where(Delivery.notification_id == id)
        db.execute(delete(Attempt).where(Attempt.delivery_id.in_(jobs)))
        db.execute(delete(Delivery).where(Delivery.notification_id == id))
        db.execute(delete(Notification).where(Notification.id == id))
        affected += 1
    audit(db, actor, "retention.deleted", {"affected": affected, "cutoff": cutoff})
    return {"affected": affected, "preview": False, "batch_limit": limit}


def housekeeping(factory):
    """One batch per invocation; transaction ownership remains explicit."""
    from notideck.security import consume_rate

    if not consume_rate(factory, "maintenance", 1, 3600):
        return
    now = time.time()
    with factory() as db:
        session_ids = list(db.scalars(select(Session.id).where(Session.expires_at < now).limit(500)))
        if session_ids:
            db.execute(delete(Session).where(Session.id.in_(session_ids), Session.expires_at < now))
        worker_ids = list(db.scalars(select(Worker.id).where(Worker.heartbeat < now - 7 * 86400).limit(500)))
        if worker_ids:
            db.execute(delete(Worker).where(Worker.id.in_(worker_ids), Worker.heartbeat < now - 7 * 86400))
        for prefixes, seconds in [(("login:", "user:"), 300), (("source:", "test:"), 60)]:
            cutoff = int(now - 86400) // seconds
            keys = list(
                db.scalars(
                    select(RateBucket.key)
                    .where(
                        or_(*(RateBucket.key.startswith(prefix) for prefix in prefixes)),
                        RateBucket.window < cutoff,
                    )
                    .limit(500)
                )
            )
            if keys:
                db.execute(delete(RateBucket).where(RateBucket.key.in_(keys), RateBucket.window < cutoff))
        if settings(db).get("retention_enabled", False):
            retain_notifications(db, "system:retention", confirm=True)
        db.commit()

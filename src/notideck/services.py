import json
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, func, update
from sqlalchemy.exc import IntegrityError

from notideck.database.models import (
    Audit,
    Channel,
    Delivery,
    Group,
    Notification,
    Recipient,
    Rule,
    Setting,
    Template,
)
from notideck.routing import matches, render
from notideck.security import digest


def audit(db, actor, operation, details=None):
    db.add(Audit(actor=actor, operation=operation, details=details or {}))


def settings(db):
    return {row.key: row.value for row in db.scalars(select(Setting))}


def set_setting(db, key, value):
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))


def serialize(row):
    result = {column.key: getattr(row, column.key) for column in row.__table__.columns}
    for key in [
        "password_hash",
        "token_hash",
        "csrf_hash",
        "credentials",
        "payload_hash",
        "webhook_secret",
        "lease_token",
    ]:
        result.pop(key, None)
    if "event_metadata" in result:
        result["metadata"] = result.pop("event_metadata")
    return result


def route_event(db, event):
    destinations = []
    matched = []
    seen = set()
    for rule in db.scalars(select(Rule).where(Rule.enabled.is_(True)).order_by(Rule.priority, Rule.id)):
        if not matches(event, rule.conditions):
            continue
        matched.append({"id": rule.id, "name": rule.name})
        for target in rule.targets:
            channel = db.get(Channel, target["channel_id"])
            if not channel or not channel.enabled:
                continue
            recipient_ids: list[str] = []
            if target.get("group_id"):
                group = db.get(Group, target["group_id"])
                recipient_ids = group.members if group else []
            if target.get("recipient_id"):
                recipient_ids = [target["recipient_id"]]
            addresses = [None] if not target.get("group_id") and not target.get("recipient_id") else []
            for rid in recipient_ids:
                recipient = db.get(Recipient, rid)
                if recipient and recipient.addresses.get(channel.provider):
                    addresses.append(recipient.addresses[channel.provider])
            for address in addresses:
                key = (channel.id, address)
                if key not in seen:
                    seen.add(key)
                    destinations.append(
                        {
                            "channel_id": channel.id,
                            "channel_name": channel.name,
                            "recipient": address,
                            "template_id": rule.template_id,
                            "priority": rule.priority,
                        }
                    )
        if rule.stop:
            break
    return matched, destinations


def ingest(db, source, payload):
    data = payload.model_dump()
    fingerprint = digest(json.dumps(data, sort_keys=True, separators=(",", ":")))
    if data.get("idempotency_key"):
        old = db.scalar(
            select(Notification).where(
                Notification.source_id == source.id, Notification.idempotency_key == data["idempotency_key"]
            )
        )
        if old:
            if old.payload_hash != fingerprint:
                raise ValueError("Idempotency key already used with a different payload")
            return old, True
    notification_id = str(uuid.uuid4())
    event = {
        **data,
        "id": notification_id,
        "source": source.name,
        "source_id": source.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _, destinations = route_event(db, event)
    values = {k: v for k, v in data.items() if k not in {"source", "metadata"}}
    notification = Notification(
        id=notification_id,
        source_id=source.id,
        payload_hash=fingerprint,
        event_metadata=data["metadata"],
        status="PENDING" if destinations else "UNROUTED",
        **values,
    )
    try:
        with db.begin_nested():
            db.add(notification)
            db.flush()
            for destination in destinations:
                rendered = dict(event)
                if destination["template_id"]:
                    template = db.get(Template, destination["template_id"])
                    if template:
                        rendered["title"] = render(template.title, event)
                        rendered["message"] = render(template.text, event)
                        rendered["html"] = render(template.html or "", event, html=True)
                db.add(
                    Delivery(
                        notification_id=notification.id,
                        channel_id=destination["channel_id"],
                        recipient=destination["recipient"],
                        priority=destination["priority"],
                        rendered=rendered,
                    )
                )
            db.flush()
    except IntegrityError:
        if not data.get("idempotency_key"):
            raise
        # Restart snapshot for MySQL REPEATABLE READ after concurrent insertion.
        db.rollback()
        old = db.scalar(
            select(Notification).where(
                Notification.source_id == source.id, Notification.idempotency_key == data["idempotency_key"]
            )
        )
        if old is None:
            raise
        if old.payload_hash != fingerprint:
            raise ValueError("Idempotency key already used with a different payload")
        return old, True
    db.commit()
    return notification, False


def update_aggregate(db, notification_id):
    db.flush()
    # Serialize aggregate updates after job transitions. MySQL uses READ COMMITTED.
    db.execute(update(Notification).where(Notification.id == notification_id).values(updated_at=time.time()))
    notification = db.get(Notification, notification_id)
    states = set(db.scalars(select(Delivery.status).where(Delivery.notification_id == notification_id)))
    if not states:
        status = "UNROUTED"
    elif states == {"SENT"}:
        status = "SENT"
    elif states & {"PENDING", "IN_PROGRESS", "RETRY_SCHEDULED"}:
        status = "PENDING"
    elif states == {"CANCELLED"}:
        status = "CANCELLED"
    elif "SENT" in states:
        status = "PARTIAL"
    else:
        status = "FAILED"
    notification.status = status
    notification.updated_at = time.time()


def counts(db, model, field):
    return {
        key: count
        for key, count in db.execute(select(field, func.count()).select_from(model).group_by(field))
    }

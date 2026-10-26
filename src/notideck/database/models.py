"""Portable schema: UUID strings, UTC Unix seconds, JSON encoded in TEXT."""

import json
import time
import uuid
from typing import Any

from sqlalchemy import Boolean, Double, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class JSONText(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value is not None else None


class Base(DeclarativeBase):
    pass


class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at: Mapped[float] = mapped_column(Double, default=time.time, index=True)


class User(Entity, Base):
    __tablename__ = "nd_users"
    username: Mapped[str] = mapped_column(String(100), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="VIEWER")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Session(Entity, Base):
    __tablename__ = "nd_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("nd_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[float] = mapped_column(Double, index=True)


class Source(Entity, Base):
    __tablename__ = "nd_sources"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text, default="", nullable=True)
    environment: Mapped[str] = mapped_column(String(100), default="production")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit: Mapped[int] = mapped_column(Integer, default=120)
    networks: Mapped[list] = mapped_column(JSONText, default=list)
    tags: Mapped[list] = mapped_column(JSONText, default=list)
    webhook_secret: Mapped[str | None] = mapped_column(Text)


class APIKey(Entity, Base):
    __tablename__ = "nd_api_keys"
    source_id: Mapped[str] = mapped_column(ForeignKey("nd_sources.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    prefix: Mapped[str] = mapped_column(String(16))
    scopes: Mapped[list] = mapped_column(JSONText, default=lambda: ["notifications:write"])
    expires_at: Mapped[float | None] = mapped_column(Double)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Channel(Entity, Base):
    __tablename__ = "nd_channels"
    name: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40))
    credentials: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    rate_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    next_send_at: Mapped[float] = mapped_column(Double, default=0)


class Recipient(Entity, Base):
    __tablename__ = "nd_recipients"
    name: Mapped[str] = mapped_column(String(200))
    addresses: Mapped[dict] = mapped_column(JSONText, default=dict)


class Group(Entity, Base):
    __tablename__ = "nd_groups"
    name: Mapped[str] = mapped_column(String(200))
    members: Mapped[list] = mapped_column(JSONText, default=list)


class Template(Entity, Base):
    __tablename__ = "nd_templates"
    name: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text, default="{{ notification.title }}")
    text: Mapped[str] = mapped_column(Text, default="{{ notification.message }}")
    html: Mapped[str | None] = mapped_column(Text, default="", nullable=True)


class Rule(Entity, Base):
    __tablename__ = "nd_rules"
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default="", nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    conditions: Mapped[list] = mapped_column(JSONText, default=list)
    targets: Mapped[list] = mapped_column(JSONText, default=list)
    stop: Mapped[bool] = mapped_column(Boolean, default=False)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("nd_templates.id"))


class Notification(Entity, Base):
    __tablename__ = "nd_notifications"
    __table_args__ = (
        UniqueConstraint("source_id", "idempotency_key", name="nd_event_idem"),
        Index("nd_event_filter", "environment", "severity", "created_at"),
    )
    source_id: Mapped[str] = mapped_column(ForeignKey("nd_sources.id"), index=True)
    external_event_id: Mapped[str | None] = mapped_column(String(200))
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    payload_hash: Mapped[str] = mapped_column(String(64))
    environment: Mapped[str] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(500))
    message: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    tags: Mapped[list] = mapped_column(JSONText, default=list)
    event_metadata: Mapped[dict] = mapped_column(JSONText, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="UNROUTED")
    updated_at: Mapped[float] = mapped_column(Double, default=time.time)


class Delivery(Entity, Base):
    __tablename__ = "nd_deliveries"
    __table_args__ = (Index("nd_job_ready", "status", "available_at", "priority"),)
    notification_id: Mapped[str] = mapped_column(ForeignKey("nd_notifications.id"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("nd_channels.id"), index=True)
    recipient: Mapped[str | None] = mapped_column(String(500))
    rendered: Mapped[dict] = mapped_column(JSONText)
    status: Mapped[str] = mapped_column(String(24), default="PENDING")
    priority: Mapped[int] = mapped_column(Integer, default=100)
    available_at: Mapped[float] = mapped_column(Double, default=time.time)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[float | None] = mapped_column(Double)
    updated_at: Mapped[float] = mapped_column(Double, default=time.time)
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    accepted_at: Mapped[float | None] = mapped_column(Double)


class Attempt(Entity, Base):
    __tablename__ = "nd_attempts"
    delivery_id: Mapped[str] = mapped_column(ForeignKey("nd_deliveries.id"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    success: Mapped[bool] = mapped_column(Boolean)
    retryable: Mapped[bool] = mapped_column(Boolean)
    code: Mapped[str | None] = mapped_column(String(50))
    error: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[float] = mapped_column(Double)


class Audit(Entity, Base):
    __tablename__ = "nd_audits"
    actor: Mapped[str] = mapped_column(String(100))
    operation: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSONText, default=dict)


class Setting(Base):
    __tablename__ = "nd_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSONText)


class Worker(Base):
    __tablename__ = "nd_workers"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    heartbeat: Mapped[float] = mapped_column(Double)
    processed: Mapped[int] = mapped_column(Integer, default=0)


class RateBucket(Base):
    __tablename__ = "nd_rate_limits"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    window: Mapped[int] = mapped_column(Integer)
    count: Mapped[int] = mapped_column(Integer)

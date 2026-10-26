from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from notideck.routing import OPS


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatabaseInput(Strict):
    engine: Literal["sqlite", "postgresql", "mysql", "oracle"] = "sqlite"
    path: str | None = None
    host: str = "localhost"
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str = "notideck"
    username: str = ""
    password: str = ""
    tls: dict[str, str] = Field(default_factory=dict)
    tls_enabled: bool | None = None
    schema_name: str | None = Field(default=None, max_length=63, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")


class SetupInput(Strict):
    database: DatabaseInput = Field(default_factory=DatabaseInput)
    username: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)
    confirm_password: str
    app_name: str = Field(default="NotiDeck", max_length=100)
    base_url: str = "http://localhost:8000"
    timezone: str = "UTC"
    retention_days: int = Field(default=90, ge=1, le=3650)
    max_attempts: int = Field(default=5, ge=1, le=20)
    retry_base: int = Field(default=10, ge=1, le=3600)


class Login(Strict):
    username: str = Field(max_length=100)
    password: str = Field(max_length=256)


class EventInput(Strict):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "environment": "production",
                    "severity": "CRITICAL",
                    "title": "Database replication lag",
                    "message": "Replication lag exceeded 120 seconds.",
                    "tags": ["postgresql"],
                    "metadata": {"lag_seconds": 120},
                    "idempotency_key": "replication-alert-123",
                }
            ]
        },
    )
    source: str | None = Field(default=None, max_length=100)
    external_event_id: str | None = Field(default=None, max_length=200)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    environment: str = Field(default="production", min_length=1, max_length=100)
    severity: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    title: str = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1, max_length=50000)
    category: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SourceInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    environment: str = Field(default="production", max_length=100)
    enabled: bool = True
    rate_limit: int = Field(default=120, ge=1, le=100000)
    networks: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("networks")
    @classmethod
    def networks_valid(cls, value):
        import ipaddress

        for network in value:
            ipaddress.ip_network(network)
        return value


class ChannelInput(Strict):
    name: str = Field(min_length=1, max_length=200)
    provider: str = Field(max_length=40)
    config: dict = Field(default_factory=dict)
    enabled: bool = True
    rate_per_minute: int = Field(default=60, ge=1, le=60000)


class Condition(Strict):
    field: str = Field(max_length=200, pattern=r"^[a-zA-Z][a-zA-Z0-9_.]*$")
    op: str
    value: Any = None

    @field_validator("op")
    @classmethod
    def valid_op(cls, value):
        if value not in OPS:
            raise ValueError("Unknown condition operator")
        return value


class Target(Strict):
    channel_id: str
    group_id: str | None = None
    recipient_id: str | None = None


class RuleInput(Strict):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    conditions: list[Condition] = Field(default_factory=list, max_length=50)
    targets: list[Target] = Field(min_length=1, max_length=100)
    stop: bool = False
    template_id: str | None = None


class UserInput(Strict):
    username: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9_.@-]+$")
    full_name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254)
    password: str | None = Field(default=None, max_length=256)
    role: Literal["ADMIN", "OPERATOR", "VIEWER"] = "VIEWER"
    enabled: bool = True


class PasswordChange(Strict):
    current_password: str = Field(max_length=256)
    password: str = Field(min_length=12, max_length=256)


class TemplatePreview(Strict):
    template: str = Field(max_length=20000)
    event: EventInput
    html: bool = False


class QueueAction(Strict):
    status: str | None = Field(default=None, max_length=24)
    ids: list[str] = Field(default_factory=list, max_length=1000)
    channel_id: str | None = None
    environment: str | None = None
    source_id: str | None = None
    severity: str | None = None
    before: float | None = None
    confirm: bool = False
    reason: str = Field(default="", max_length=500)

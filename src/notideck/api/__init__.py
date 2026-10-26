"""Versioned HTTP API. Cookie mutations require CSRF; machine ingestion uses scoped keys."""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import asdict
from typing import Any
from importlib.resources import files
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from jinja2 import TemplateError

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import URL
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from notideck import __version__
from notideck.config import Config
from notideck.database import engine_for, migrate, schema_current, sessions
from notideck.database.models import (
    APIKey,
    Attempt,
    Audit,
    Channel,
    Delivery,
    Group,
    Notification,
    Recipient,
    Rule,
    Session,
    Setting,
    Source,
    Template,
    User,
    Worker,
)
from notideck.providers import registry
from notideck.template_library import install_database_templates
from notideck.routing import render
from notideck.schemas import (
    ChannelInput,
    DatabaseInput,
    EventInput,
    Login,
    QueueAction,
    PasswordChange,
    TemplatePreview,
    RuleInput,
    SetupInput,
    SourceInput,
    UserInput,
)
from notideck.security import consume_rate, digest, hasher, password_hash, verify_password
from notideck.services import (
    audit,
    counts,
    ingest,
    route_event,
    serialize,
    set_setting,
    settings,
    update_aggregate,
)

log = logging.getLogger("notideck.api")
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def database_url(config, value: DatabaseInput):
    if value.engine == "sqlite":
        return URL.create(
            "sqlite", database=value.path or str(config.data_dir / "notideck.db")
        ).render_as_string(hide_password=False)
    drivers = {"postgresql": "postgresql+psycopg", "mysql": "mysql+pymysql", "oracle": "oracle+oracledb"}
    allowed = {
        "postgresql": {"sslmode", "sslrootcert", "sslcert", "sslkey"},
        "mysql": {"ssl_ca", "ssl_cert", "ssl_key"},
        "oracle": {"config_dir", "wallet_location", "wallet_password"},
    }
    if set(value.tls) - allowed[value.engine]:
        raise ValueError("Unsupported TLS parameter")
    query = dict(value.tls)
    if value.tls_enabled is not None:
        if value.engine != "postgresql":
            raise ValueError(
                "The TLS checkbox is supported for PostgreSQL; use driver TLS options for other databases"
            )
        if not value.tls_enabled:
            if query:
                raise ValueError("Remove TLS parameters when TLS is disabled")
            query["sslmode"] = "disable"
        else:
            query.setdefault("sslmode", "verify-full")
            if query["sslmode"] not in {"require", "verify-ca", "verify-full"}:
                raise ValueError("Enabled TLS requires require, verify-ca or verify-full mode")
    if value.schema_name:
        if value.engine != "postgresql":
            raise ValueError("Custom schema is supported only for PostgreSQL; Oracle uses account ownership")
        query["options"] = "-csearch_path=" + value.schema_name
    if value.engine == "oracle":
        query["service_name"] = value.database
    return URL.create(
        drivers[value.engine],
        username=value.username,
        password=value.password,
        host=value.host,
        port=value.port,
        database=None if value.engine == "oracle" else value.database,
        query=query,
    ).render_as_string(hide_password=False)


def create_app(config: Config | None = None):
    config = config or Config()
    app = FastAPI(
        title="NotiDeck", version=__version__, docs_url=None, redoc_url=None, openapi_url="/api/openapi.json"
    )
    app.state.config = config
    app.state.engine = None
    app.state.factory = None
    app.state.providers = registry()

    def connect():
        if app.state.factory is None:
            config.reload()
            if config.database_url:
                engine = engine_for(config.database_url)
                if schema_current(engine):
                    app.state.engine = engine
                    app.state.factory = sessions(engine)
                else:
                    engine.dispose()
        return app.state.factory

    def db_session():
        try:
            factory = connect()
        except Exception:
            raise HTTPException(
                503, "Database unavailable; check configuration and migration status"
            ) from None
        if factory is None:
            raise HTTPException(503, "Setup or database migration required")
        with factory() as db:
            yield db

    def initialized():
        factory = connect()
        if not factory:
            return False
        with factory() as db:
            return bool(db.get(Setting, "initialized"))

    def bootstrap(request: Request):
        supplied = request.headers.get("X-Bootstrap-Token", "").strip()
        if not secrets.compare_digest(
            supplied.encode(), config.token_path.read_text(encoding="utf-8").strip().encode()
        ):
            raise HTTPException(
                403,
                "Bootstrap token missing or incorrect. Use the bootstrap.token file from this running installation, not a source API key or account password.",
            )
        if initialized():
            raise HTTPException(409, "Setup already completed")

    def current(request: Request, db=Depends(db_session)):
        token = request.cookies.get("nd_session", "")
        session = db.scalar(
            select(Session).where(Session.token_hash == digest(token), Session.expires_at > time.time())
        )
        user = db.get(User, session.user_id) if session else None
        if not user or not user.enabled:
            raise HTTPException(401, "Authentication required")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            csrf = request.headers.get("X-CSRF-Token", "")
            if not secrets.compare_digest(digest(csrf), session.csrf_hash):
                raise HTTPException(403, "CSRF token missing or invalid")
        request.state.user = user
        return user

    def permission(level="read"):
        def dependency(user=Depends(current)):
            roles = {
                "read": {"ADMIN", "OPERATOR", "VIEWER"},
                "operate": {"ADMIN", "OPERATOR"},
                "admin": {"ADMIN"},
            }
            if user.role not in roles[level]:
                raise HTTPException(403, "Insufficient permission")
            return user

        return dependency

    read, operate, admin = permission(), permission("operate"), permission("admin")

    def get(db, model, id):
        row = db.get(model, id)
        if row is None:
            raise HTTPException(404, "Record not found")
        return row

    @app.middleware("http")
    async def envelope(request: Request, call_next):
        request_id = str(uuid.uuid4())
        start = time.monotonic()
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"error": {"message": "Cross-site mutation rejected"}}, status_code=403)
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.url.netloc}":
                return JSONResponse(
                    {"error": {"message": "Cross-origin request rejected", "request_id": request_id}},
                    status_code=403,
                )
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 262144:
                    return JSONResponse(
                        {"error": {"message": "Request exceeds 256 KiB", "request_id": request_id}},
                        status_code=413,
                    )
            request._body = bytes(body)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers.update(
            {
                "X-Request-ID": request_id,
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
                "Referrer-Policy": "no-referrer",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
                "Cache-Control": "no-store",
            }
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        log.info(
            json.dumps(
                {
                    "event": "request",
                    "request_id": request_id,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - start) * 1000, 2),
                }
            )
        )
        return response

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        return JSONResponse(
            {"error": {"message": exc.detail, "request_id": getattr(request.state, "request_id", None)}},
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Never echo inputs: validation payloads may contain passwords or keys.
        return JSONResponse(
            {
                "error": {
                    "message": "Request validation failed",
                    "fields": [{"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()],
                }
            },
            status_code=422,
        )

    @app.exception_handler(TemplateError)
    async def template_error(request, exc):
        return JSONResponse(
            {"error": {"message": "Invalid template or missing template variable"}}, status_code=422
        )

    @app.exception_handler(ValueError)
    async def bad_value(request, exc):
        return JSONResponse({"error": {"message": str(exc)}}, status_code=422)

    @app.exception_handler(IntegrityError)
    async def conflict(request, exc):
        return JSONResponse(
            {"error": {"message": "Record conflicts with an existing record or reference"}}, status_code=409
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        return JSONResponse(
            {"error": {"message": "Database operation failed; check database availability"}}, status_code=503
        )

    @app.get("/api/docs", response_class=HTMLResponse, include_in_schema=False)
    def api_docs():
        return """<!doctype html><html><head><title>NotiDeck API</title>
        <link rel="stylesheet" href="/api-docs/swagger-ui.css"></head><body>
        <div id="swagger-ui"></div><script src="/api-docs/swagger-ui-bundle.js"></script>
        <script src="/api-docs/init.js"></script></body></html>"""

    prefix = "/api/v1"

    @app.get(prefix + "/health/live")
    def live():
        return {"status": "alive"}

    @app.get(prefix + "/health/ready")
    def ready(db=Depends(db_session)):
        db.execute(text("SELECT 1 FROM DUAL" if db.bind.dialect.name == "oracle" else "SELECT 1"))
        if not db.get(Setting, "initialized"):
            raise HTTPException(503, "Setup required")
        return {"status": "ready"}

    @app.get(prefix + "/system/version")
    def version():
        return {"version": __version__}

    @app.get(prefix + "/setup/status")
    def setup_status():
        return {"initialized": initialized(), "version": __version__}

    @app.post(prefix + "/setup/verify", dependencies=[Depends(bootstrap)])
    def verify_bootstrap():
        return {"verified": True}

    @app.post(prefix + "/setup/test", dependencies=[Depends(bootstrap)])
    def test_database(value: DatabaseInput):
        engine = None
        try:
            engine = engine_for(database_url(config, value))
            with engine.connect() as conn:
                conn.execute(text("SELECT 1 FROM DUAL" if value.engine == "oracle" else "SELECT 1"))
            return {"connected": True, "note": "DDL privileges are verified during initialization."}
        except Exception:
            raise HTTPException(
                422,
                "Connection failed. Check driver extra, hostname, credentials, service name and TLS settings.",
            ) from None
        finally:
            if engine:
                engine.dispose()

    @app.post(prefix + "/setup", dependencies=[Depends(bootstrap)])
    def setup(value: SetupInput):
        if value.password != value.confirm_password:
            raise HTTPException(422, "Passwords do not match")
        hashed = password_hash(value.password)
        ZoneInfo(value.timezone)
        if urlsplit(value.base_url).scheme not in {"http", "https"}:
            raise ValueError("Base URL must use HTTP or HTTPS")
        with config.lock:
            if initialized():
                raise HTTPException(409, "Setup already completed")
            url = database_url(config, value.database)
            engine = engine_for(url)
            try:
                migrate(engine)
                factory = sessions(engine)
                with factory() as db:
                    if db.get(Setting, "initialized") or db.scalar(select(func.count()).select_from(User)):
                        raise HTTPException(409, "Selected database already contains an installation")
                    # Save connection before committing initialization: a crash can always reconnect.
                    config.save_database(url)
                    user = User(
                        username=value.username,
                        full_name=value.full_name,
                        email=value.email,
                        password_hash=hashed,
                        role="ADMIN",
                    )
                    db.add(user)
                    db.add(
                        Template(
                            **json.loads(
                                files("notideck")
                                .joinpath("templates/default.json")
                                .read_text(encoding="utf-8")
                            )
                        )
                    )
                    install_database_templates(db, value.username)
                    for key in [
                        "app_name",
                        "base_url",
                        "timezone",
                        "retention_days",
                        "max_attempts",
                        "retry_base",
                    ]:
                        set_setting(db, key, getattr(value, key))
                    set_setting(db, "initialized", True)
                    set_setting(db, "dispatch_paused", False)
                    audit(db, value.username, "setup.completed")
                    db.commit()
                if app.state.engine:
                    app.state.engine.dispose()
                app.state.engine, app.state.factory = engine, factory
            except HTTPException:
                engine.dispose()
                raise
            except Exception:
                engine.dispose()
                raise HTTPException(
                    422,
                    "Initialization failed. Verify database DDL privileges and installed driver; existing data was not reset.",
                ) from None
        return {"initialized": True}

    @app.post(prefix + "/auth/login")
    def login(value: Login, request: Request, response: Response, db=Depends(db_session)):
        remote = request.client.host if request.client else "unknown"
        factory = app.state.factory
        if not consume_rate(factory, "login:" + digest(remote), 10, 300) or not consume_rate(
            factory, "user:" + digest(value.username), 20, 300
        ):
            raise HTTPException(429, "Too many login attempts; try again in five minutes")
        user = db.scalar(select(User).where(User.username == value.username))
        valid = verify_password(user.password_hash if user else DUMMY_HASH, value.password)
        if not valid or not user or not user.enabled:
            audit(db, "anonymous", "login.failed")
            db.commit()
            raise HTTPException(401, "Invalid credentials")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.add(
            Session(
                user_id=user.id,
                token_hash=digest(token),
                csrf_hash=digest(csrf),
                expires_at=time.time() + 28800,
            )
        )
        audit(db, user.id, "login")
        db.commit()
        secure = request.url.scheme == "https" or os.getenv("NOTIDECK_SECURE_COOKIES") == "1"
        response.set_cookie(
            "nd_session", token, httponly=True, secure=secure, samesite="strict", max_age=28800
        )
        response.set_cookie("nd_csrf", csrf, httponly=False, secure=secure, samesite="strict", max_age=28800)
        return {"user": serialize(user), "csrf_token": csrf}

    @app.get(prefix + "/auth/me")
    def me(user=Depends(read)):
        return serialize(user)

    @app.post(prefix + "/auth/logout")
    def logout(request: Request, response: Response, user=Depends(read), db=Depends(db_session)):
        db.execute(delete(Session).where(Session.token_hash == digest(request.cookies.get("nd_session", ""))))
        db.commit()
        response.delete_cookie("nd_session")
        response.delete_cookie("nd_csrf")
        return {"logged_out": True}

    @app.post(prefix + "/auth/password")
    def change_password(value: PasswordChange, user=Depends(read), db=Depends(db_session)):
        if not verify_password(user.password_hash, value.current_password):
            raise HTTPException(403, "Current password incorrect")
        user.password_hash = password_hash(value.password)
        db.execute(delete(Session).where(Session.user_id == user.id))
        audit(db, user.id, "password.changed")
        db.commit()
        return {"changed": True, "login_required": True}

    @app.get(prefix + "/system/display")
    def display_settings(user=Depends(read), db=Depends(db_session)):
        values = settings(db)
        return {"app_name": values.get("app_name", "NotiDeck"), "timezone": values.get("timezone", "UTC")}

    @app.get(prefix + "/providers")
    def providers(user=Depends(read)):
        return [
            {
                "id": name,
                "schema": provider.configuration_schema(),
                "capabilities": provider.supported_capabilities(),
            }
            for name, provider in app.state.providers.items()
        ]

    def page(db, model, query=None, offset=0, limit=50):
        if offset < 0 or not 1 <= limit <= 100:
            raise HTTPException(422, "Pagination requires offset >= 0 and limit 1–100")
        query = query if query is not None else select(model)
        total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
        items = db.scalars(query.order_by(model.created_at.desc()).offset(offset).limit(limit)).all()
        return {"items": [serialize(row) for row in items], "total": total, "offset": offset, "limit": limit}

    @app.get(prefix + "/channels")
    def channels(offset: int = 0, limit: int = 50, user=Depends(read), db=Depends(db_session)):
        return page(db, Channel, offset=offset, limit=limit)

    @app.get(prefix + "/channels/{id}")
    def channel(id: str, user=Depends(operate), db=Depends(db_session)):
        row = get(db, Channel, id)
        result = serialize(row)
        values = json.loads(config.decrypt(row.credentials))
        result["config"] = {
            key: "••••••••"
            if app.state.providers[row.provider]
            .configuration_schema()
            .get("properties", {})
            .get(key, {})
            .get("secret", True)
            else value
            for key, value in values.items()
        }
        return result

    def save_channel(value, db, actor, row=None):
        provider = app.state.providers.get(value.provider)
        if not provider:
            raise HTTPException(422, "Unknown provider")
        credentials = value.config
        if row:
            old = json.loads(config.decrypt(row.credentials))
            credentials = {k: old.get(k) if v == "••••••••" else v for k, v in credentials.items()}
        validated = provider.validate_configuration(credentials)
        values = value.model_dump(exclude={"config"})
        values["credentials"] = config.encrypt(json.dumps(validated))
        if row:
            for key, val in values.items():
                setattr(row, key, val)
        else:
            row = Channel(**values)
            db.add(row)
        db.flush()
        audit(db, actor.id, "channel.saved", {"id": row.id, "name": row.name, "provider": row.provider})
        db.commit()
        return serialize(row)

    @app.post(prefix + "/channels", status_code=201)
    def create_channel(value: ChannelInput, user=Depends(operate), db=Depends(db_session)):
        return save_channel(value, db, user)

    @app.patch(prefix + "/channels/{id}")
    def edit_channel(id: str, value: ChannelInput, user=Depends(operate), db=Depends(db_session)):
        return save_channel(value, db, user, get(db, Channel, id))

    @app.post(prefix + "/channels/{id}/test")
    def test_channel(id: str, user=Depends(operate), db=Depends(db_session)):
        row = get(db, Channel, id)
        if not consume_rate(app.state.factory, "test:" + id, 5):
            raise HTTPException(429, "Channel test limit exceeded")
        result = app.state.providers[row.provider].test_connection(
            json.loads(config.decrypt(row.credentials))
        )
        audit(db, user.id, "channel.tested", {"id": id, "success": result.success})
        db.commit()
        return asdict(result)

    @app.post(prefix + "/channels/{id}/duplicate", status_code=201)
    def duplicate_channel(id: str, user=Depends(operate), db=Depends(db_session)):
        original = get(db, Channel, id)
        row = Channel(
            name=(original.name + " (copy)")[:200],
            provider=original.provider,
            credentials=original.credentials,
            enabled=False,
            rate_per_minute=original.rate_per_minute,
        )
        db.add(row)
        db.flush()
        audit(db, user.id, "channel.duplicated", {"id": row.id, "original_id": id})
        db.commit()
        return serialize(row)

    @app.delete(prefix + "/channels/{id}")
    def delete_channel(id: str, user=Depends(admin), db=Depends(db_session)):
        row = get(db, Channel, id)
        referenced = any(any(t["channel_id"] == id for t in r.targets) for r in db.scalars(select(Rule)))
        if referenced or db.scalar(
            select(func.count()).select_from(Delivery).where(Delivery.channel_id == id)
        ):
            raise HTTPException(409, "Channel is referenced by rules or history; disable it instead")
        db.delete(row)
        audit(db, user.id, "channel.deleted", {"id": id})
        db.commit()
        return {"deleted": True}

    @app.get(prefix + "/routes")
    def routes(offset: int = 0, limit: int = 50, user=Depends(read), db=Depends(db_session)):
        return page(db, Rule, select(Rule).order_by(Rule.priority, Rule.id), offset, limit)

    def save_rule(value, db, user, row=None):
        for target in value.targets:
            get(db, Channel, target.channel_id)
            if target.recipient_id:
                get(db, Recipient, target.recipient_id)
            if target.group_id:
                get(db, Group, target.group_id)
        if value.template_id:
            get(db, Template, value.template_id)
        if row:
            for key, val in value.model_dump().items():
                setattr(row, key, val)
        else:
            row = Rule(**value.model_dump())
            db.add(row)
        db.flush()
        audit(db, user.id, "route.saved", {"id": row.id, "name": row.name})
        db.commit()
        return serialize(row)

    @app.post(prefix + "/routes", status_code=201)
    def create_rule(value: RuleInput, user=Depends(operate), db=Depends(db_session)):
        return save_rule(value, db, user)

    @app.patch(prefix + "/routes/{id}")
    def edit_rule(id: str, value: RuleInput, user=Depends(operate), db=Depends(db_session)):
        return save_rule(value, db, user, get(db, Rule, id))

    @app.post(prefix + "/routes/simulate")
    def simulate(value: EventInput, user=Depends(operate), db=Depends(db_session)):
        event = value.model_dump()
        if value.source:
            source = db.scalar(
                select(Source).where((Source.name == value.source) | (Source.id == value.source))
            )
            if source:
                event.update(source=source.name, source_id=source.id)
                if "environment" not in value.model_fields_set:
                    event["environment"] = source.environment
        matched, destinations = route_event(db, event)
        return {"rules": matched, "destinations": destinations}

    @app.get(prefix + "/sources")
    def sources(offset: int = 0, limit: int = 50, user=Depends(read), db=Depends(db_session)):
        return page(db, Source, offset=offset, limit=limit)

    @app.post(prefix + "/sources", status_code=201)
    def create_source(value: SourceInput, user=Depends(admin), db=Depends(db_session)):
        row = Source(**value.model_dump())
        db.add(row)
        db.flush()
        audit(db, user.id, "source.created", {"id": row.id})
        db.commit()
        return serialize(row)

    @app.patch(prefix + "/sources/{id}")
    def edit_source(id: str, value: SourceInput, user=Depends(admin), db=Depends(db_session)):
        row = get(db, Source, id)
        for key, val in value.model_dump().items():
            setattr(row, key, val)
        audit(db, user.id, "source.updated", {"id": id})
        db.commit()
        return serialize(row)

    @app.get(prefix + "/sources/{id}/keys")
    def list_keys(id: str, user=Depends(admin), db=Depends(db_session)):
        return [serialize(row) for row in db.scalars(select(APIKey).where(APIKey.source_id == id))]

    @app.post(prefix + "/sources/{id}/keys", status_code=201)
    def create_key(id: str, value: dict, user=Depends(admin), db=Depends(db_session)):
        get(db, Source, id)
        scopes = value.get("scopes", ["notifications:write"])
        if not isinstance(scopes, list) or set(scopes) - {"notifications:write"}:
            raise HTTPException(422, "Unsupported API key scopes")
        expiry = value.get("expires_at")
        if expiry is not None and (not isinstance(expiry, (int, float)) or expiry <= time.time()):
            raise HTTPException(422, "Expiration must be a future UTC epoch timestamp")
        name = value.get("name", "API key")
        if not isinstance(name, str) or not 1 <= len(name) <= 100:
            raise HTTPException(422, "Key name must be 1–100 characters")
        token = "nd_" + secrets.token_urlsafe(32)
        row = APIKey(
            source_id=id,
            name=name,
            scopes=scopes,
            token_hash=digest(token),
            prefix=token[:10],
            expires_at=expiry,
        )
        db.add(row)
        audit(db, user.id, "key.created", {"source_id": id})
        db.commit()
        return {**serialize(row), "key": token}

    @app.post(prefix + "/keys/{id}/revoke")
    def revoke_key(id: str, user=Depends(admin), db=Depends(db_session)):
        get(db, APIKey, id).revoked = True
        audit(db, user.id, "key.revoked", {"id": id})
        db.commit()
        return {"revoked": True}

    @app.post(prefix + "/sources/{id}/webhook-secret")
    def webhook_secret(id: str, user=Depends(admin), db=Depends(db_session)):
        source = get(db, Source, id)
        secret = secrets.token_urlsafe(32)
        source.webhook_secret = config.encrypt(secret)
        audit(db, user.id, "webhook_secret.rotated", {"source_id": id})
        db.commit()
        return {"secret": secret}

    def source_access(source, request):
        if not source.enabled:
            raise HTTPException(403, "Source disabled")
        remote = request.client.host if request.client else ""
        if source.networks:
            try:
                allowed = any(
                    ipaddress.ip_address(remote) in ipaddress.ip_network(net) for net in source.networks
                )
            except ValueError:
                allowed = False
            if not allowed:
                raise HTTPException(403, "Source network not allowed")
        if not consume_rate(app.state.factory, "source:" + source.id, source.rate_limit):
            raise HTTPException(429, "Source rate limit exceeded")

    def machine(request: Request, db=Depends(db_session)):
        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Bearer API key required")
        key = db.scalar(
            select(APIKey).where(APIKey.token_hash == digest(authorization[7:]), APIKey.revoked.is_(False))
        )
        if not key or (key.expires_at and key.expires_at <= time.time()):
            raise HTTPException(401, "API key invalid or expired")
        if "notifications:write" not in key.scopes:
            raise HTTPException(403, "Missing notifications:write scope")
        source = get(db, Source, key.source_id)
        source_access(source, request)
        return source

    def accept(value, source, db):
        if value.source and value.source not in {source.name, source.id}:
            raise HTTPException(403, "API key is scoped to a different source")
        if "environment" not in value.model_fields_set:
            value = value.model_copy(update={"environment": source.environment})
        try:
            row, replayed = ingest(db, source, value)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return {"id": row.id, "status": row.status, "replayed": replayed}

    @app.post(prefix + "/notifications", status_code=202)
    def post_notification(value: EventInput, source=Depends(machine), db=Depends(db_session)):
        return accept(value, source, db)

    @app.post(prefix + "/webhooks/{source_id}", status_code=202)
    async def webhook(source_id: str, request: Request, db=Depends(db_session)):
        # Raw bytes read asynchronously, database work delegated explicitly to a thread.
        from starlette.concurrency import run_in_threadpool

        body = await request.body()

        def receive():
            source = get(db, Source, source_id)
            timestamp = request.headers.get("X-NotiDeck-Timestamp", "")
            try:
                valid_time = abs(time.time() - int(timestamp)) <= 300
            except ValueError:
                valid_time = False
            if not valid_time or not source.webhook_secret:
                raise HTTPException(401, "Webhook authentication failed")
            expected = hmac.new(
                config.decrypt(source.webhook_secret).encode(),
                timestamp.encode() + b"." + body,
                hashlib.sha256,
            ).hexdigest()
            if not secrets.compare_digest(expected, request.headers.get("X-NotiDeck-Signature", "")):
                raise HTTPException(401, "Webhook authentication failed")
            source_access(source, request)
            try:
                value = EventInput.model_validate_json(body)
            except ValueError:
                raise HTTPException(422, "Webhook payload validation failed") from None
            if not value.idempotency_key:
                raise HTTPException(422, "Signed webhooks require an idempotency_key for replay protection")
            return accept(value, source, db)

        return await run_in_threadpool(receive)

    @app.get(prefix + "/notifications")
    def notifications(
        offset: int = 0,
        limit: int = 50,
        severity: str | None = None,
        environment: str | None = None,
        source_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        user=Depends(read),
        db=Depends(db_session),
    ):
        query = select(Notification)
        for field, value in [
            (Notification.severity, severity),
            (Notification.environment, environment),
            (Notification.source_id, source_id),
            (Notification.status, status),
        ]:
            if value:
                query = query.where(field == value)
        if search:
            query = query.where(Notification.title.contains(search, autoescape=True))
        return page(db, Notification, query, offset, limit)

    @app.get(prefix + "/notifications/{id}")
    def notification(id: str, user=Depends(read), db=Depends(db_session)):
        return serialize(get(db, Notification, id))

    @app.get(prefix + "/notifications/{id}/deliveries")
    def deliveries(id: str, user=Depends(read), db=Depends(db_session)):
        get(db, Notification, id)
        return [
            {
                **serialize(row),
                "attempt_history": [
                    serialize(a)
                    for a in db.scalars(
                        select(Attempt).where(Attempt.delivery_id == row.id).order_by(Attempt.number)
                    )
                ],
            }
            for row in db.scalars(select(Delivery).where(Delivery.notification_id == id))
        ]

    def filtered_queue(value):
        query = select(Delivery).join(Notification)
        if value.status:
            query = query.where(Delivery.status == value.status)
        if value.ids:
            query = query.where(Delivery.id.in_(value.ids))
        for field, val in [
            (Delivery.channel_id, value.channel_id),
            (Notification.environment, value.environment),
            (Notification.source_id, value.source_id),
            (Notification.severity, value.severity),
        ]:
            if val:
                query = query.where(field == val)
        if value.before:
            query = query.where(Delivery.created_at < value.before)
        return query

    @app.get(prefix + "/queue")
    def queue(
        offset: int = 0,
        limit: int = 50,
        status: str | None = None,
        channel_id: str | None = None,
        environment: str | None = None,
        source_id: str | None = None,
        severity: str | None = None,
        before: float | None = None,
        user=Depends(read),
        db=Depends(db_session),
    ):
        query = filtered_queue(
            QueueAction(
                channel_id=channel_id,
                environment=environment,
                source_id=source_id,
                severity=severity,
                before=before,
            )
        )
        if status:
            query = query.where(Delivery.status == status)
        return page(db, Delivery, query, offset, limit)

    @app.get(prefix + "/queue/stats")
    def queue_stats(user=Depends(read), db=Depends(db_session)):
        now = time.time()
        oldest = db.scalar(
            select(func.min(Delivery.created_at)).where(Delivery.status.in_(["PENDING", "RETRY_SCHEDULED"]))
        )
        return {
            "counts": counts(db, Delivery, Delivery.status),
            "paused": settings(db).get("dispatch_paused", False),
            "oldest_pending_seconds": now - oldest if oldest else 0,
            "dispatch_per_minute": db.scalar(
                select(func.count()).select_from(Attempt).where(Attempt.created_at >= now - 60)
            ),
            "channel_backlog": dict(
                db.execute(
                    select(Delivery.channel_id, func.count())
                    .where(Delivery.status.in_(["PENDING", "RETRY_SCHEDULED"]))
                    .group_by(Delivery.channel_id)
                ).all()
            ),
            "workers": [
                {
                    "id": w.id,
                    "heartbeat": w.heartbeat,
                    "processed": w.processed,
                    "healthy": w.heartbeat > now - 60,
                }
                for w in db.scalars(select(Worker))
            ],
        }

    @app.get(prefix + "/dashboard")
    def dashboard(user=Depends(read), db=Depends(db_session)):
        return {
            "notifications": db.scalar(select(func.count()).select_from(Notification)),
            "severity": counts(db, Notification, Notification.severity),
            "deliveries": counts(db, Delivery, Delivery.status),
            "channels": db.scalar(select(func.count()).select_from(Channel)),
            "recent": page(db, Notification, limit=8)["items"],
        }

    @app.post(prefix + "/queue/{action}")
    def queue_action(action: str, value: QueueAction, user=Depends(operate), db=Depends(db_session)):
        if action in {"pause", "resume"}:
            if value.channel_id:
                get(db, Channel, value.channel_id).paused = action == "pause"
            else:
                set_setting(db, "dispatch_paused", action == "pause")
            audit(db, user.id, "queue." + action, value.model_dump(exclude={"confirm"}))
            db.commit()
            return {"paused": action == "pause"}
        if action not in {"retry", "cancel", "clear"}:
            raise HTTPException(404, "Unknown queue operation")
        if action in {"clear", "cancel"} and user.role != "ADMIN":
            raise HTTPException(403, "Queue cancellation requires administrator permission")
        eligible = ["FAILED", "DEAD_LETTER"] if action == "retry" else ["PENDING", "RETRY_SCHEDULED"]
        query = filtered_queue(value).where(Delivery.status.in_(eligible))
        count = db.scalar(select(func.count()).select_from(query.subquery()))
        if not value.confirm:
            return {
                "preview": True,
                "affected": count,
                "note": "In-progress sends cannot always be recalled. History is retained.",
            }
        # Conditional updates exclude jobs claimed since preview; commit one audited transaction.
        affected = 0
        parents = set()
        for job in db.scalars(query):
            values = {"status": "PENDING" if action == "retry" else "CANCELLED", "updated_at": time.time()}
            if action == "retry":
                values.update(available_at=time.time(), attempts=0)
            result = db.execute(
                update(Delivery).where(Delivery.id == job.id, Delivery.status.in_(eligible)).values(**values)
            )
            affected += result.rowcount
            if result.rowcount:
                parents.add(job.notification_id)
        for parent in parents:
            update_aggregate(db, parent)
        audit(
            db,
            user.id,
            "queue." + action,
            {"filters": value.model_dump(exclude={"confirm"}), "affected": affected},
        )
        db.commit()
        return {"affected": affected}

    @app.get(prefix + "/users")
    def users(offset: int = 0, limit: int = 50, user=Depends(admin), db=Depends(db_session)):
        return page(db, User, offset=offset, limit=limit)

    @app.post(prefix + "/users", status_code=201)
    def create_user(value: UserInput, user=Depends(admin), db=Depends(db_session)):
        if not value.password:
            raise HTTPException(422, "Password required")
        row = User(**value.model_dump(exclude={"password"}), password_hash=password_hash(value.password))
        db.add(row)
        audit(db, user.id, "user.created", {"username": value.username, "role": value.role})
        db.commit()
        return serialize(row)

    @app.patch(prefix + "/users/{id}")
    def edit_user(id: str, value: UserInput, user=Depends(admin), db=Depends(db_session)):
        row = get(db, User, id)
        if id == user.id and (not value.enabled or value.role != "ADMIN"):
            raise HTTPException(409, "Cannot disable or demote your own administrator account")
        for key, val in value.model_dump(exclude={"password"}).items():
            setattr(row, key, val)
        if value.password:
            row.password_hash = password_hash(value.password)
        db.execute(delete(Session).where(Session.user_id == id))
        audit(db, user.id, "user.updated", {"id": id, "role": value.role, "enabled": value.enabled})
        db.commit()
        return serialize(row)

    # Small relational resources share transport; each still validates its domain fields.
    resource_models = {"recipients": Recipient, "groups": Group, "templates": Template}

    @app.get(prefix + "/resources/{kind}")
    def resource_list(
        kind: str, offset: int = 0, limit: int = 50, user=Depends(read), db=Depends(db_session)
    ):
        if kind not in resource_models:
            raise HTTPException(404, "Unknown resource")
        return page(db, resource_models[kind], offset=offset, limit=limit)

    def save_resource(kind, value, db, user, id=None):
        if kind not in resource_models:
            raise HTTPException(404, "Unknown resource")
        allowed = {
            "recipients": {"name", "addresses"},
            "groups": {"name", "members"},
            "templates": {"name", "title", "text", "html"},
        }[kind]
        if (
            set(value) - allowed
            or not isinstance(value.get("name"), str)
            or not 1 <= len(value["name"]) <= 200
        ):
            raise HTTPException(422, "Invalid resource fields or name")
        if kind == "recipients":
            addresses = value.get("addresses", {})
            if not isinstance(addresses, dict) or any(
                not isinstance(v, str) or len(v) > 500 for v in addresses.values()
            ):
                raise HTTPException(422, "Addresses must map provider names to destination strings")
        if kind == "groups":
            if not isinstance(value.get("members", []), list):
                raise HTTPException(422, "Members must be recipient IDs")
            for member in value.get("members", []):
                get(db, Recipient, member)
        if kind == "templates":
            for field in ["title", "text", "html"]:
                if field in value:
                    render(
                        value[field],
                        {
                            "id": "sample",
                            "title": "Sample",
                            "message": "Message",
                            "severity": "INFO",
                            "environment": "test",
                            "source": "sample",
                            "created_at": "2026-01-01",
                            "metadata": {},
                        },
                        html=field == "html",
                    )
        model = resource_models[kind]
        row: Any = get(db, model, id) if id else model()
        for key, val in value.items():
            setattr(row, key, val)
        db.add(row)
        db.flush()
        audit(db, user.id, kind + ".saved", {"id": row.id})
        db.commit()
        return serialize(row)

    @app.post(prefix + "/resources/{kind}", status_code=201)
    def create_resource(kind: str, value: dict, user=Depends(operate), db=Depends(db_session)):
        return save_resource(kind, value, db, user)

    @app.patch(prefix + "/resources/{kind}/{id}")
    def edit_resource(kind: str, id: str, value: dict, user=Depends(operate), db=Depends(db_session)):
        return save_resource(kind, value, db, user, id)

    @app.post(prefix + "/templates/preview")
    def preview_template(value: TemplatePreview, user=Depends(operate)):
        return {"result": render(value.template, value.event.model_dump(), html=value.html)}

    @app.get(prefix + "/audits")
    def audits(
        offset: int = 0,
        limit: int = 50,
        operation: str | None = None,
        user=Depends(admin),
        db=Depends(db_session),
    ):
        query = select(Audit)
        if operation:
            query = query.where(Audit.operation.contains(operation, autoescape=True))
        return page(db, Audit, query, offset, limit)

    @app.get(prefix + "/settings")
    def get_settings(user=Depends(admin), db=Depends(db_session)):
        return {
            "retention_enabled": False,
            **settings(db),
            "database": db.bind.dialect.name,
            "version": __version__,
        }

    @app.patch(prefix + "/settings")
    def edit_settings(value: dict, user=Depends(admin), db=Depends(db_session)):
        if set(value) - {
            "app_name",
            "base_url",
            "timezone",
            "retention_days",
            "retention_enabled",
            "max_attempts",
            "retry_base",
        }:
            raise HTTPException(422, "Unknown setting")
        for key, val in value.items():
            if key == "retention_enabled":
                if not isinstance(val, bool):
                    raise HTTPException(422, "Automatic retention must be true or false")
            elif key in {"retention_days", "max_attempts", "retry_base"}:
                maximum = {"retention_days": 3650, "max_attempts": 20, "retry_base": 3600}[key]
                if type(val) is not int or not 1 <= val <= maximum:
                    raise HTTPException(422, "Setting outside permitted range")
            elif not isinstance(val, str) or len(val) > 500:
                raise HTTPException(422, "Invalid setting")
            if key == "timezone":
                try:
                    ZoneInfo(val)
                except (ZoneInfoNotFoundError, ValueError):
                    raise HTTPException(422, "Unknown timezone") from None
            if key == "base_url" and urlsplit(val).scheme not in {"http", "https"}:
                raise HTTPException(422, "Invalid base URL")
            set_setting(db, key, val)
        audit(db, user.id, "settings.updated", {"fields": list(value)})
        db.commit()
        return settings(db)

    @app.post(prefix + "/retention")
    def retention(value: QueueAction, user=Depends(admin), db=Depends(db_session)):
        from notideck.maintenance import retain_notifications

        result = retain_notifications(db, user.id, confirm=value.confirm)
        if value.confirm:
            db.commit()
        return result

    @app.get(prefix + "/metrics", response_class=PlainTextResponse)
    def metrics(user=Depends(admin), db=Depends(db_session)):
        values = counts(db, Delivery, Delivery.status)
        lines = ["# TYPE notideck_deliveries gauge"]
        lines.extend(f'notideck_deliveries{{status="{key}"}} {value}' for key, value in values.items())
        lines += [
            "# TYPE notideck_attempt_errors gauge",
            f"notideck_attempt_errors {db.scalar(select(func.count()).select_from(Attempt).where(Attempt.success.is_(False)))}",
            "# TYPE notideck_attempt_duration_ms gauge",
            f"notideck_attempt_duration_ms {db.scalar(select(func.avg(Attempt.duration_ms))) or 0}",
        ]
        return "\n".join(lines) + "\n"

    static = files("notideck").joinpath("static")

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        from pathlib import Path

        root = Path(str(static)).resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root) or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        if candidate.is_file():
            return FileResponse(candidate)
        if "." in path:
            raise HTTPException(404, "Asset not found")
        if not (root / "index.html").exists():
            raise HTTPException(503, "Console assets missing; run frontend production build")
        return FileResponse(root / "index.html")

    return app

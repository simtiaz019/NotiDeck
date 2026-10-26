from importlib.resources import files
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

REVISION = "0002"


def engine_for(url: str):
    parsed = make_url(url)
    if parsed.get_backend_name() not in {"sqlite", "postgresql", "mysql", "oracle"}:
        raise ValueError("Unsupported database dialect")
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if parsed.get_backend_name() == "mysql":
        kwargs["isolation_level"] = "READ COMMITTED"
        kwargs["connect_args"] = {"connect_timeout": 10}
    elif parsed.get_backend_name() == "postgresql":
        kwargs["connect_args"] = {"connect_timeout": 10}
    if parsed.get_backend_name() == "sqlite":
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
        if parsed.database and parsed.database != ":memory:":
            path = Path(parsed.database)
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.touch(mode=0o600, exist_ok=True)
            path.chmod(0o600)
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def pragmas(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")

    return engine


def migrate(engine):
    config = AlembicConfig()
    config.set_main_option("script_location", str(files("notideck").joinpath("migrations")))
    with engine.begin() as conn:
        config.attributes["connection"] = conn
        command.upgrade(config, "head")


def schema_current(engine):
    with engine.connect() as conn:
        if not inspect(conn).has_table("alembic_version"):
            return False
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == REVISION


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)

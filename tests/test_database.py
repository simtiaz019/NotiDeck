import os
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql, oracle, postgresql, sqlite
import pytest

from notideck.database import engine_for, migrate, schema_current
from notideck.database.models import Base


def test_migration_idempotent(tmp_path):
    engine = engine_for("sqlite:///" + str(tmp_path / "migration.db"))
    migrate(engine)
    migrate(engine)
    assert schema_current(engine)
    assert "nd_deliveries" in inspect(engine).get_table_names()
    engine.dispose()


@pytest.mark.parametrize(
    "dialect", [sqlite.dialect(), postgresql.dialect(), mysql.dialect(), oracle.dialect()]
)
def test_schema_compiles_for_dialects(dialect):
    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=dialect))


@pytest.mark.skipif(
    not os.getenv("NOTIDECK_TEST_DATABASE_URL"), reason="Live external database not configured"
)
def test_external_database_migration():
    engine = engine_for(os.environ["NOTIDECK_TEST_DATABASE_URL"])
    migrate(engine)
    assert schema_current(engine)
    # Dedicated disposable test DB only; never use an application database.
    with engine.begin() as connection:
        from sqlalchemy import insert, select, delete
        from notideck.database.models import Setting

        connection.execute(delete(Setting).where(Setting.key == "integration-probe"))
        connection.execute(insert(Setting).values(key="integration-probe", value={"portable": True}))
        assert connection.execute(
            select(Setting.value).where(Setting.key == "integration-probe")
        ).scalar() == {"portable": True}
        connection.execute(delete(Setting).where(Setting.key == "integration-probe"))
    engine.dispose()


def test_upgrade_preserves_existing_sqlite_data(tmp_path):
    from alembic import command
    from alembic.config import Config
    from importlib.resources import files
    from sqlalchemy import text

    engine = engine_for("sqlite:///" + str(tmp_path / "upgrade.db"))
    config = Config()
    config.set_main_option("script_location", str(files("notideck").joinpath("migrations")))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0001")
        connection.execute(
            text("INSERT INTO nd_settings (key, value) VALUES (:key, :value)"),
            {"key": "upgrade-marker", "value": '{"preserved": true}'},
        )
    assert not schema_current(engine)
    migrate(engine)
    assert schema_current(engine)
    with engine.connect() as connection:
        assert (
            "preserved"
            in connection.execute(text("SELECT value FROM nd_settings WHERE key='upgrade-marker'")).scalar()
        )
    engine.dispose()

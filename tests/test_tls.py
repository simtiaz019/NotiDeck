import pytest
from sqlalchemy.engine import make_url
from notideck.api import database_url
from notideck.schemas import DatabaseInput


def test_postgres_tls_disabled(config):
    url = make_url(
        database_url(config, DatabaseInput(engine="postgresql", tls_enabled=False, password="a@:/#?b"))
    )
    assert url.query["sslmode"] == "disable"
    assert url.password == "a@:/#?b"


def test_postgres_tls_enabled_requires_verification_by_default(config):
    url = make_url(database_url(config, DatabaseInput(engine="postgresql", tls_enabled=True)))
    assert url.query["sslmode"] == "verify-full"
    with pytest.raises(ValueError):
        database_url(config, DatabaseInput(engine="postgresql", tls_enabled=True, tls={"sslmode": "prefer"}))
    with pytest.raises(ValueError):
        database_url(
            config, DatabaseInput(engine="postgresql", tls_enabled=False, tls={"sslmode": "require"})
        )


def test_legacy_tls_options_remain_compatible(config):
    url = make_url(database_url(config, DatabaseInput(engine="postgresql", tls={"sslmode": "disable"})))
    assert url.query["sslmode"] == "disable"

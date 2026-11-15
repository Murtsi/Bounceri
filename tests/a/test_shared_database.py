import pytest

from bouncer.db.store import shared_database_url


def test_shared_database_allows_driver_alias_and_explicit_traffic_override(monkeypatch):
    monkeypatch.setenv("BOUNCER_DATABASE_URL", "postgresql+psycopg://user:secret@host/db")
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", "sqlite:///other.db")
    assert shared_database_url("postgresql://user:secret@host/db") == (
        "postgresql://user:secret@host/db"
    )


@pytest.mark.parametrize("traffic,cases", [
    (None, "sqlite:///private.db"), ("sqlite:///private.db", None),
    ("sqlite:///private.db", "sqlite:///other.db"), ("bad-private-canary", "bad-private-canary"),
])
def test_shared_database_rejects_missing_different_and_malformed_urls_safely(
    monkeypatch, traffic, cases,
):
    for key, value in (("BOUNCER_TRAFFIC_DATABASE_URL", traffic), ("BOUNCER_DATABASE_URL", cases)):
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    with pytest.raises(ValueError) as error:
        shared_database_url()
    assert "private-canary" not in str(error.value)


@pytest.mark.parametrize("url", [
    "sqlite://", "sqlite:///:memory:", "sqlite:///file::memory:",
    "sqlite:///file:private-canary?mode=memory&cache=shared&uri=true",
    "sqlite:///private-canary.db?uri=true", "postgresql://user:private-canary@host",
    "postgresql://user:private-canary@host/",
])
def test_shared_database_rejects_transient_or_implicit_database_urls(monkeypatch, url):
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    with pytest.raises(ValueError) as error:
        shared_database_url()
    assert "private-canary" not in str(error.value)


def test_shared_database_accepts_postgres_unix_socket_with_explicit_database(monkeypatch):
    url = "postgresql+psycopg:///private-study?host=/var/run/postgresql"
    monkeypatch.setenv("BOUNCER_TRAFFIC_DATABASE_URL", url)
    monkeypatch.setenv("BOUNCER_DATABASE_URL", url)
    assert shared_database_url() == url

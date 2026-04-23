"""
Shared fixtures for EyeGila integration tests.

Tests run against a live stack (docker compose up).  The DATABASE_URL /
API_URL can be overridden via environment variables so the same suite works
locally and in CI.

  DATABASE_URL  postgresql://postgres:postgres@localhost:5433/traffic
  API_URL       http://localhost:8000
  ADMIN_USER    admin
  ADMIN_PASS    admin
"""
import os
import pytest
import requests

API_URL    = os.getenv("API_URL",   "http://localhost:8000")
DB_URL     = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/traffic")
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "admin")


@pytest.fixture(scope="session")
def api():
    """Base requests Session with the API URL pre-set."""
    s = requests.Session()
    s.base_url = API_URL  # type: ignore[attr-defined]
    return s


@pytest.fixture(scope="session")
def token(api):
    """Authenticate once per test session and return the Bearer token."""
    r = api.post(f"{API_URL}/login",
                 json={"username": ADMIN_USER, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth(token):
    """Requests Session with auth header pre-set."""
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="session")
def db():
    """SQLAlchemy session connected directly to the test DB (port 5433)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()

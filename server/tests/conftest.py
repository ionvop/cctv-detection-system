from fastapi.testclient import TestClient
from common.database import Base, get_db
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from server.main import app
import pytest
import os


TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def superuser_client(client):
    """Client with SUPER_KEY header pre-set."""
    os.environ["SUPER_KEY"] = "test-super-key"
    client.headers.update({"Authorization": "Bearer test-super-key"})
    return client


@pytest.fixture()
def auth_client(superuser_client, db):
    """Creates a user, logs in, and returns a separate authenticated client.

    Uses a new TestClient so the shared `client` fixture is not mutated —
    tests that request both `client` (unauthenticated) and a fixture that
    depends on `auth_client` will therefore keep a clean unauthenticated client.
    """
    os.environ["SUPER_KEY"] = "test-super-key"
    superuser_client.post("/users/", json={"username": "testuser", "password": "testpass"})
    resp = superuser_client.post("/login/", json={"username": "testuser", "password": "testpass"})
    token = resp.json()["token"]

    with TestClient(app) as auth_c:
        auth_c.headers.update({"Authorization": f"Bearer {token}"})
        yield auth_c
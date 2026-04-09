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
def auth_client(superuser_client, client, db):
    """Creates a user, logs in, and returns an authenticated client."""
    # Create user via superuser endpoint
    superuser_client.post("/users/", json={"username": "testuser", "password": "testpass"})

    # Log in to get a token
    resp = client.post("/login/", json={"username": "testuser", "password": "testpass"})
    token = resp.json()["token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client
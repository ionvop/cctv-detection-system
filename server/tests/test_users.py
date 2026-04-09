def test_create_user(superuser_client):
    resp = superuser_client.post("/users/", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"


def test_create_duplicate_user(superuser_client):
    superuser_client.post("/users/", json={"username": "alice", "password": "secret"})
    resp = superuser_client.post("/users/", json={"username": "alice", "password": "secret"})
    assert resp.status_code == 400


def test_get_users(superuser_client):
    superuser_client.post("/users/", json={"username": "alice", "password": "secret"})
    resp = superuser_client.get("/users/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_users_requires_superuser(client):
    resp = client.get("/users/", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401
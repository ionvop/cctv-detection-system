def test_login_success(superuser_client, client):
    superuser_client.post("/users/", json={"username": "bob", "password": "pass123"})
    resp = client.post("/login/", json={"username": "bob", "password": "pass123"})
    assert resp.status_code == 200
    assert "token" in resp.json()


def test_login_wrong_password(superuser_client, client):
    superuser_client.post("/users/", json={"username": "bob", "password": "pass123"})
    resp = client.post("/login/", json={"username": "bob", "password": "wrongpass"})
    assert resp.status_code == 401


def test_logout(auth_client):
    resp = auth_client.delete("/login/")
    assert resp.status_code == 200
    assert resp.json() == {"detail": "Logged out"}
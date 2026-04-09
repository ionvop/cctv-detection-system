import pytest


@pytest.fixture()
def intersection(auth_client):
    return auth_client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    }).json()


def test_create_street(auth_client, intersection):
    resp = auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Main St"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Main St"
    assert data["intersection_id"] == intersection["id"]


def test_create_street_requires_auth(client, intersection):
    resp = client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Main St"
    })
    assert resp.status_code == 403


def test_get_streets_empty(client):
    resp = client.get("/streets/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_streets(auth_client, client, intersection):
    auth_client.post("/streets/", json={"intersection_id": intersection["id"], "name": "Main St"})
    auth_client.post("/streets/", json={"intersection_id": intersection["id"], "name": "2nd Ave"})
    resp = client.get("/streets/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_street(auth_client, client, intersection):
    created = auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Main St"
    }).json()
    resp = client.get(f"/streets/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Main St"


def test_get_street_not_found(client):
    resp = client.get("/streets/999")
    assert resp.status_code == 404


def test_update_street(auth_client, intersection):
    created = auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Old St"
    }).json()
    resp = auth_client.put(f"/streets/{created['id']}", json={"name": "New St"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New St"


def test_update_street_not_found(auth_client):
    resp = auth_client.put("/streets/999", json={"name": "X"})
    assert resp.status_code == 404


def test_update_street_requires_auth(client):
    resp = client.put("/streets/1", json={"name": "X"})
    assert resp.status_code == 403


def test_delete_street(auth_client, client, intersection):
    created = auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "To Delete"
    }).json()
    resp = auth_client.delete(f"/streets/{created['id']}")
    assert resp.status_code == 200
    assert client.get(f"/streets/{created['id']}").status_code == 404


def test_delete_street_not_found(auth_client):
    resp = auth_client.delete("/streets/999")
    assert resp.status_code == 404


def test_delete_street_requires_auth(client):
    resp = client.delete("/streets/1")
    assert resp.status_code == 403


def test_delete_intersection_cascades_to_streets(auth_client, client, intersection):
    created = auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Main St"
    }).json()
    auth_client.delete(f"/intersections/{intersection['id']}")
    assert client.get(f"/streets/{created['id']}").status_code == 404
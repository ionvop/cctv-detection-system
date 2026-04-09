def test_create_intersection(auth_client):
    resp = auth_client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Main & 1st"
    assert data["latitude"] == 7.07
    assert data["longitude"] == 125.6
    assert "id" in data
    assert "time" in data


def test_create_intersection_requires_auth(client):
    resp = client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    })
    assert resp.status_code == 401


def test_get_intersections_empty(client):
    resp = client.get("/intersections/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_intersections(auth_client, client):
    auth_client.post("/intersections/", json={"name": "A", "latitude": 1.0, "longitude": 2.0})
    auth_client.post("/intersections/", json={"name": "B", "latitude": 3.0, "longitude": 4.0})
    resp = client.get("/intersections/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_intersection(auth_client, client):
    created = auth_client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    }).json()
    resp = client.get(f"/intersections/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Main & 1st"


def test_get_intersection_not_found(client):
    resp = client.get("/intersections/999")
    assert resp.status_code == 404


def test_update_intersection(auth_client):
    created = auth_client.post("/intersections/", json={
        "name": "Old Name", "latitude": 7.07, "longitude": 125.6
    }).json()
    resp = auth_client.put(f"/intersections/{created['id']}", json={
        "name": "New Name", "latitude": 8.0, "longitude": 126.0
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "New Name"
    assert data["latitude"] == 8.0


def test_update_intersection_not_found(auth_client):
    resp = auth_client.put("/intersections/999", json={"name": "X"})
    assert resp.status_code == 404


def test_update_intersection_requires_auth(client):
    resp = client.put("/intersections/1", json={"name": "X"})
    assert resp.status_code == 401


def test_delete_intersection(auth_client, client):
    created = auth_client.post("/intersections/", json={
        "name": "To Delete", "latitude": 7.07, "longitude": 125.6
    }).json()
    resp = auth_client.delete(f"/intersections/{created['id']}")
    assert resp.status_code == 200
    assert client.get(f"/intersections/{created['id']}").status_code == 404


def test_delete_intersection_not_found(auth_client):
    resp = auth_client.delete("/intersections/999")
    assert resp.status_code == 404


def test_delete_intersection_requires_auth(client):
    resp = client.delete("/intersections/1")
    assert resp.status_code == 401
import pytest


@pytest.fixture()
def intersection(auth_client):
    return auth_client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    }).json()


@pytest.fixture()
def cctv(auth_client, intersection):
    return auth_client.post("/cctvs/", json={
        "intersection_id": intersection["id"],
        "name": "Cam 1",
        "rtsp_url": "rtsp://example.com/stream1"
    }).json()


def test_create_cctv(auth_client, intersection):
    resp = auth_client.post("/cctvs/", json={
        "intersection_id": intersection["id"],
        "name": "Cam 1",
        "rtsp_url": "rtsp://example.com/stream1"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Cam 1"
    assert data["rtsp_url"] == "rtsp://example.com/stream1"
    assert data["intersection_id"] == intersection["id"]


def test_create_cctv_requires_auth(client, intersection):
    resp = client.post("/cctvs/", json={
        "intersection_id": intersection["id"],
        "name": "Cam 1",
        "rtsp_url": "rtsp://example.com/stream1"
    })
    assert resp.status_code == 401


def test_get_cctvs_empty(client):
    resp = client.get("/cctvs/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_cctvs(auth_client, client, cctv):
    resp = client.get("/cctvs/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_cctv(client, cctv):
    resp = client.get(f"/cctvs/{cctv['id']}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Cam 1"


def test_get_cctv_not_found(client):
    resp = client.get("/cctvs/999")
    assert resp.status_code == 404


def test_update_cctv(auth_client, cctv):
    resp = auth_client.put(f"/cctvs/{cctv['id']}", json={
        "name": "Cam 1 Updated",
        "rtsp_url": "rtsp://example.com/stream2"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Cam 1 Updated"
    assert data["rtsp_url"] == "rtsp://example.com/stream2"


def test_update_cctv_not_found(auth_client):
    resp = auth_client.put("/cctvs/999", json={"name": "X", "rtsp_url": "rtsp://x.com"})
    assert resp.status_code == 404


def test_update_cctv_requires_auth(client, cctv):
    resp = client.put(f"/cctvs/{cctv['id']}", json={"name": "X"})
    assert resp.status_code == 401


def test_delete_cctv(auth_client, client, cctv):
    resp = auth_client.delete(f"/cctvs/{cctv['id']}")
    assert resp.status_code == 200
    assert client.get(f"/cctvs/{cctv['id']}").status_code == 404


def test_delete_cctv_not_found(auth_client):
    resp = auth_client.delete("/cctvs/999")
    assert resp.status_code == 404


def test_delete_cctv_requires_auth(client, cctv):
    resp = client.delete(f"/cctvs/{cctv['id']}")
    assert resp.status_code == 401


def test_delete_intersection_cascades_to_cctvs(auth_client, client, intersection, cctv):
    auth_client.delete(f"/intersections/{intersection['id']}")
    assert client.get(f"/cctvs/{cctv['id']}").status_code == 404
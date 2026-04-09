import pytest


@pytest.fixture()
def intersection(auth_client):
    return auth_client.post("/intersections/", json={
        "name": "Main & 1st", "latitude": 7.07, "longitude": 125.6
    }).json()


@pytest.fixture()
def street(auth_client, intersection):
    return auth_client.post("/streets/", json={
        "intersection_id": intersection["id"], "name": "Main St"
    }).json()


@pytest.fixture()
def cctv(auth_client, intersection):
    return auth_client.post("/cctvs/", json={
        "intersection_id": intersection["id"],
        "name": "Cam 1",
        "rtsp_url": "rtsp://example.com/stream1"
    }).json()


SAMPLE_POINTS = [{"x": 10, "y": 20}, {"x": 30, "y": 40}, {"x": 50, "y": 60}]


def test_create_region(auth_client, cctv, street):
    resp = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"],
        "street_id": street["id"],
        "region_points": SAMPLE_POINTS
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["cctv_id"] == cctv["id"]
    assert data["street_id"] == street["id"]
    assert len(data["region_points"]) == 3


def test_create_region_requires_auth(client, cctv, street):
    resp = client.post("/regions/", json={
        "cctv_id": cctv["id"],
        "street_id": street["id"],
        "region_points": SAMPLE_POINTS
    })
    assert resp.status_code == 401


def test_get_regions_empty(client):
    resp = client.get("/regions/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_regions(auth_client, client, cctv, street):
    auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    })
    auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    })
    resp = client.get("/regions/")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_region(auth_client, client, cctv, street):
    created = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    }).json()
    resp = client.get(f"/regions/{created['id']}")
    assert resp.status_code == 200


def test_get_region_not_found(client):
    resp = client.get("/regions/999")
    assert resp.status_code == 404


def test_update_region(auth_client, cctv, street):
    created = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    }).json()
    new_points = [{"x": 1, "y": 2}, {"x": 3, "y": 4}]
    resp = auth_client.put(f"/regions/{created['id']}", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": new_points
    })
    assert resp.status_code == 200
    assert len(resp.json()["region_points"]) == 2


def test_update_region_not_found(auth_client, cctv, street):
    resp = auth_client.put("/regions/999", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    })
    assert resp.status_code == 404


def test_update_region_requires_auth(client, auth_client, cctv, street):
    created = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    }).json()
    resp = client.put(f"/regions/{created['id']}", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    })
    assert resp.status_code == 401


def test_delete_cctv_cascades_to_regions(auth_client, client, cctv, street):
    created = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    }).json()
    auth_client.delete(f"/cctvs/{cctv['id']}")
    assert client.get(f"/regions/{created['id']}").status_code == 404


def test_delete_street_cascades_to_regions(auth_client, client, cctv, street):
    created = auth_client.post("/regions/", json={
        "cctv_id": cctv["id"], "street_id": street["id"], "region_points": SAMPLE_POINTS
    }).json()
    auth_client.delete(f"/streets/{street['id']}")
    assert client.get(f"/regions/{created['id']}").status_code == 404
"""Camera CRUD and status tests."""
import pytest
from tests.conftest import API_URL


@pytest.fixture
def intersection(auth):
    r = auth.post(f"{API_URL}/intersections/",
                  json={"name": "_cam_test_inter", "latitude": 7.44, "longitude": 125.80})
    obj = r.json()
    yield obj
    auth.delete(f"{API_URL}/intersections/{obj['id']}")


@pytest.fixture
def camera(auth, intersection):
    r = auth.post(f"{API_URL}/cctvs/",
                  json={"name": "_test_cam", "rtsp_url": "rtsp://127.0.0.1:8554/test",
                        "intersection_id": intersection["id"]})
    assert r.status_code == 200
    obj = r.json()
    yield obj
    auth.delete(f"{API_URL}/cctvs/{obj['id']}")


def test_create_camera(auth, intersection):
    r = auth.post(f"{API_URL}/cctvs/",
                  json={"name": "_create_test", "rtsp_url": "rtsp://0.0.0.0:554/x",
                        "intersection_id": intersection["id"]})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "_create_test"
    assert data["status"] in ("online", "offline", "reconnecting")
    auth.delete(f"{API_URL}/cctvs/{data['id']}")


def test_list_cameras(auth, camera):
    r = auth.get(f"{API_URL}/cctvs/")
    assert r.status_code == 200
    ids = [c["id"] for c in r.json()]
    assert camera["id"] in ids


def test_get_camera(auth, camera):
    r = auth.get(f"{API_URL}/cctvs/{camera['id']}")
    assert r.status_code == 200
    assert r.json()["name"] == "_test_cam"


def test_get_camera_404(auth):
    r = auth.get(f"{API_URL}/cctvs/999999")
    assert r.status_code == 404


def test_update_camera(auth, camera):
    r = auth.put(f"{API_URL}/cctvs/{camera['id']}",
                 json={"name": "_test_cam_renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "_test_cam_renamed"


def test_camera_status_field_present(auth, camera):
    r = auth.get(f"{API_URL}/cctvs/{camera['id']}")
    data = r.json()
    assert "status" in data
    assert data["status"] in ("online", "offline", "reconnecting")


def test_camera_offline_when_no_heartbeat(auth, camera):
    """A newly created camera with no worker heartbeat must be offline."""
    r = auth.get(f"{API_URL}/cctvs/{camera['id']}")
    assert r.json()["status"] == "offline"

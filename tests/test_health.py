"""Health, metrics, and infrastructure tests."""
import requests
from tests.conftest import API_URL


def test_health_ok():
    r = requests.get(f"{API_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_metrics_endpoint(auth):
    r = auth.get(f"{API_URL}/metrics/workers")
    assert r.status_code == 200
    assert "worker_camera_fps" in r.text
    assert "worker_camera_claimed" in r.text


def test_prometheus_metrics():
    r = requests.get(f"{API_URL}/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text

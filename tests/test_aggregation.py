"""Aggregation history and SSE stream tests."""
import json
import time
import threading
from datetime import datetime, timezone, timedelta
import requests
import pytest
from tests.conftest import API_URL


def test_history_requires_auth():
    now = datetime.now(timezone.utc)
    r = requests.get(f"{API_URL}/aggregation/history",
                     params={"start": (now - timedelta(days=1)).isoformat(),
                             "end": now.isoformat()})
    assert r.status_code in (401, 403)


def test_history_returns_list(auth):
    now = datetime.now(timezone.utc)
    r = auth.get(f"{API_URL}/aggregation/history",
                 params={"start": (now - timedelta(days=1)).isoformat(),
                         "end": now.isoformat(),
                         "bucket": "hour"})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_history_row_shape(auth):
    now = datetime.now(timezone.utc)
    r = auth.get(f"{API_URL}/aggregation/history",
                 params={"start": (now - timedelta(days=7)).isoformat(),
                         "end": now.isoformat(),
                         "bucket": "day"})
    assert r.status_code == 200
    rows = r.json()
    if rows:
        row = rows[0]
        assert "intersection_id" in row
        assert "intersection_name" in row
        assert "object_type" in row
        assert "window_start" in row
        assert "count" in row
        assert isinstance(row["count"], int)


def test_history_bucket_hour(auth):
    now = datetime.now(timezone.utc)
    r = auth.get(f"{API_URL}/aggregation/history",
                 params={"start": (now - timedelta(hours=24)).isoformat(),
                         "end": now.isoformat(),
                         "bucket": "hour"})
    assert r.status_code == 200


def test_history_bucket_week(auth):
    now = datetime.now(timezone.utc)
    r = auth.get(f"{API_URL}/aggregation/history",
                 params={"start": (now - timedelta(days=30)).isoformat(),
                         "end": now.isoformat(),
                         "bucket": "week"})
    assert r.status_code == 200


def test_sse_stream_requires_token():
    r = requests.get(f"{API_URL}/aggregation/stream", stream=True, timeout=3)
    assert r.status_code in (401, 403, 422)


def test_sse_stream_delivers_event(token):
    """Connect to SSE, wait up to 10s for the first data event."""
    first_event = threading.Event()
    error: list[str] = []

    def consume():
        try:
            with requests.get(
                f"{API_URL}/aggregation/stream?token={token}",
                stream=True,
                timeout=(5, 12),
            ) as resp:
                if resp.status_code != 200:
                    error.append(f"status={resp.status_code}")
                    return
                for line in resp.iter_lines():
                    if line and line.startswith(b"data:"):
                        try:
                            json.loads(line[5:])
                            first_event.set()
                            return
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            error.append(str(e))

    t = threading.Thread(target=consume, daemon=True)
    t.start()
    received = first_event.wait(timeout=12)
    assert not error, f"SSE error: {error}"
    assert received, "No SSE event received within 12 seconds"

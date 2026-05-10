"""
EyeGila Demo Script
===================
Interactive demo tool for live presentations.  Drives the system through
common scenarios so the dashboard looks alive without real cameras.

Modes
-----
live        Stream realistic detections into the DB at a configurable rate.
            The SSE dashboard updates in real time.

cctv        CCTV lifecycle demo: add cameras via API, pause, update, delete.

video       Upload a video file and poll its processing status live.

all         Run live + cctv + video sequentially (full demo).

Usage
-----
# 1. Stream live detections for 2 minutes at ~10 detections/sec per camera
python scripts/demo.py live --duration 120 --rate 10

# 2. CCTV add/update/delete demo via the API
python scripts/demo.py cctv

# 3. Upload a video file and watch it process
python scripts/demo.py video --file /path/to/clip.mp4 --intersection-id 1

# 4. Full demo (live 60s + cctv + video)
python scripts/demo.py all --file /path/to/clip.mp4

Options
-------
--api-url   Base URL of the server  (default: http://localhost:8000)
--username  API username             (default: admin)
--password  API password             (default: admin)
--duration  Seconds for live mode    (default: 60)
--rate      Detections per sec per camera  (default: 8)
"""

import argparse
import random
import sys
import time
from datetime import datetime, timezone, timedelta

import requests

sys.path.append(".")

from common.database import SessionLocal
from common.models import CCTV, Detection, DetectionInRegion, Intersection, Region

# ---------------------------------------------------------------------------
# Traffic patterns (same as fake_detections.py)
# ---------------------------------------------------------------------------

OBJECT_TYPES = ["tricycle", "motorcycle", "car", "truck", "pedicab", "pedestrian"]

WEIGHTS = {
    "tricycle":   0.35,
    "motorcycle": 0.30,
    "car":        0.15,
    "truck":      0.05,
    "pedicab":    0.10,
    "pedestrian": 0.05,
}

HOUR_MULTIPLIERS = {
    0: 0.04, 1: 0.02, 2: 0.02, 3: 0.02, 4: 0.05, 5: 0.15,
    6: 0.45, 7: 0.85, 8: 1.00, 9: 0.70, 10: 0.60, 11: 0.65,
    12: 0.75, 13: 0.60, 14: 0.55, 15: 0.65, 16: 0.85, 17: 1.00,
    18: 0.90, 19: 0.70, 20: 0.50, 21: 0.35, 22: 0.20, 23: 0.10,
}

DEMO_CCTVS = [
    {
        "name": "Demo Cam – North Approach",
        "rtsp_url": "rtsp://192.168.254.104:8554/cam1",
        "intersection_id": None,   # filled at runtime
    },
    {
        "name": "Demo Cam – South Approach",
        "rtsp_url": "rtsp://192.168.254.104:8554/cam2",
        "intersection_id": None,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def random_object_type() -> str:
    types, probs = zip(*WEIGHTS.items())
    return random.choices(list(types), weights=list(probs), k=1)[0]


def random_bbox():
    x1 = round(random.uniform(0.05, 0.65), 4)
    y1 = round(random.uniform(0.05, 0.65), 4)
    return x1, y1, round(min(x1 + random.uniform(0.05, 0.25), 1.0), 4), round(min(y1 + random.uniform(0.05, 0.25), 1.0), 4)


def hour_factor() -> float:
    h = datetime.now().hour
    return HOUR_MULTIPLIERS.get(h, 0.5)


def color(code: str, text: str) -> str:
    codes = {"green": "\033[32m", "yellow": "\033[33m", "cyan": "\033[36m",
             "red": "\033[31m", "bold": "\033[1m", "reset": "\033[0m"}
    return f"{codes.get(code, '')}{text}{codes['reset']}"


def sep(title: str = ""):
    line = "─" * 60
    if title:
        pad = (58 - len(title)) // 2
        print(f"\n┌{'─' * (pad)}  {color('bold', title)}  {'─' * (60 - pad - len(title) - 4)}┐")
    else:
        print(f"\n{'─' * 62}")


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login(api_url: str, username: str, password: str) -> str:
    r = requests.post(f"{api_url}/login", json={"username": username, "password": password}, timeout=10)
    r.raise_for_status()
    token = r.json()["token"]
    print(color("green", f"  ✓ Logged in as {username}"))
    return token


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Live detection streaming
# ---------------------------------------------------------------------------

def run_live(args):
    sep("LIVE DETECTION STREAM")
    print(f"  Duration : {args.duration}s")
    print(f"  Rate     : ~{args.rate} detections/sec per camera")
    print(f"  Target   : TimescaleDB via SQLAlchemy (bypasses API for throughput)")

    db = SessionLocal()
    try:
        # Collect all camera/region pairs in the DB
        pairs: list[tuple[int, int]] = []
        for region in db.query(Region).all():
            pairs.append((region.cctv_id, region.id))

        if not pairs:
            print(color("red", "  ✗ No cameras/regions found.  Run --seed first."))
            return

        print(f"  Cameras  : {len(pairs)} camera/region pair(s)\n")

        deadline = time.monotonic() + args.duration
        interval = 1.0          # flush every second
        total_inserted = 0
        tick = 0

        while time.monotonic() < deadline:
            tick_start = time.monotonic()
            batch_detections = []
            batch_links = []

            factor = hour_factor() * random.uniform(0.85, 1.15)

            for cctv_id, region_id in pairs:
                count = max(1, round(args.rate * factor))
                now = datetime.now(timezone.utc)

                for _ in range(count):
                    x1, y1, x2, y2 = random_bbox()
                    d = Detection(
                        cctv_id=cctv_id,
                        track_id=random.randint(1, 99999),
                        object_type=random_object_type(),
                        confidence=round(random.uniform(0.68, 0.99), 4),
                        x1=x1, y1=y1, x2=x2, y2=y2,
                        time=now - timedelta(seconds=random.uniform(0, interval)),
                    )
                    batch_detections.append(d)

            db.add_all(batch_detections)
            db.flush()

            for d, (_, region_id) in zip(batch_detections, pairs * (len(batch_detections) // len(pairs) + 1)):
                batch_links.append(DetectionInRegion(region_id=region_id, detection_id=d.id, time=d.time))

            db.add_all(batch_links)
            db.commit()

            total_inserted += len(batch_detections)
            tick += 1
            elapsed = args.duration - (deadline - time.monotonic())

            rate_actual = total_inserted / elapsed if elapsed > 0 else 0
            remaining = max(0, deadline - time.monotonic())

            print(
                f"  [{elapsed:5.1f}s] "
                f"+{len(batch_detections):3d} detections  "
                f"total={color('cyan', f'{total_inserted:,}')}  "
                f"rate={color('green', f'{rate_actual:.0f}/s')}  "
                f"remaining={remaining:.0f}s",
                end="\r",
            )

            sleep_time = interval - (time.monotonic() - tick_start)
            if sleep_time > 0:
                time.sleep(sleep_time)

        print(f"\n\n  {color('green', '✓')} Done.  Inserted {total_inserted:,} detections over {args.duration}s.")
        print("    SSE dashboard updates within 5s.  Aggregation view refreshes within ~1 min.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# CCTV lifecycle demo
# ---------------------------------------------------------------------------

def run_cctv(args):
    sep("CCTV LIFECYCLE DEMO")
    token = login(args.api_url, args.username, args.password)
    hdrs  = auth_headers(token)

    # Resolve a valid intersection to attach the demo cameras to
    r = requests.get(f"{args.api_url}/intersections/", timeout=10)
    r.raise_for_status()
    intersections = r.json()
    if not intersections:
        print(color("red", "  ✗ No intersections found.  Run --seed first."))
        return

    int_id = intersections[0]["id"]
    int_name = intersections[0]["name"]
    print(f"  Attaching demo cameras to: {color('cyan', int_name)} (id={int_id})\n")

    created_ids: list[int] = []

    # Step 1 – Add cameras
    print(color("bold", "  Step 1 of 3 – Creating cameras"))
    for spec in DEMO_CCTVS:
        payload = {
            "name":            spec["name"],
            "rtsp_url":        spec["rtsp_url"],
            "intersection_id": int_id,
        }
        r = requests.post(f"{args.api_url}/cctvs/", json=payload, headers=hdrs, timeout=10)
        r.raise_for_status()
        cam = r.json()
        created_ids.append(cam["id"])
        print(f"    {color('green', '+')} id={cam['id']}  {cam['name']}  {cam['rtsp_url']}")

    print(f"\n  {color('yellow', '⏳')} Pausing 5s so you can see the cameras appear in the UI …")
    time.sleep(5)

    # Step 2 – Update one camera name + URL
    print(f"\n{color('bold', '  Step 2 of 3 – Updating first camera')}")
    cam_id = created_ids[0]
    new_name = "Demo Cam – North Approach (Updated)"
    r = requests.put(
        f"{args.api_url}/cctvs/{cam_id}",
        json={"name": new_name, "rtsp_url": "rtsp://192.168.254.104:8554/cam3"},
        headers=hdrs, timeout=10,
    )
    r.raise_for_status()
    updated = r.json()
    print(f"    {color('cyan', '✎')} id={updated['id']}  {updated['name']}  {updated['rtsp_url']}")

    print(f"\n  {color('yellow', '⏳')} Pausing 5s …")
    time.sleep(5)

    # Step 3 – Delete all demo cameras
    print(f"\n{color('bold', '  Step 3 of 3 – Deleting demo cameras')}")
    for cam_id in created_ids:
        r = requests.delete(f"{args.api_url}/cctvs/{cam_id}", headers=hdrs, timeout=10)
        r.raise_for_status()
        print(f"    {color('red', '−')} id={cam_id} deleted")

    print(f"\n  {color('green', '✓')} CCTV demo complete.")


# ---------------------------------------------------------------------------
# Video upload + poll
# ---------------------------------------------------------------------------

def run_video(args):
    sep("VIDEO UPLOAD & PROCESSING")

    if not args.file:
        print(color("red", "  ✗ --file is required for video mode."))
        return

    import os
    if not os.path.isfile(args.file):
        print(color("red", f"  ✗ File not found: {args.file}"))
        return

    token = login(args.api_url, args.username, args.password)
    hdrs  = auth_headers(token)

    # Resolve intersection
    int_id = args.intersection_id
    if int_id is None:
        r = requests.get(f"{args.api_url}/intersections/", timeout=10)
        r.raise_for_status()
        ints = r.json()
        if ints:
            int_id = ints[0]["id"]
            print(f"  Using intersection id={int_id} ({ints[0]['name']})")

    # Upload
    recorded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    print(f"  Uploading {color('cyan', args.file)} …", end="", flush=True)

    with open(args.file, "rb") as fh:
        files = {"file": (os.path.basename(args.file), fh, "video/mp4")}
        data  = {"recorded_at": recorded_at}
        if int_id:
            data["intersection_id"] = str(int_id)

        t0 = time.monotonic()
        r = requests.post(f"{args.api_url}/videos/upload", files=files, data=data, headers=hdrs, timeout=120)
        elapsed = time.monotonic() - t0

    r.raise_for_status()
    resp = r.json()
    video_id = resp["video_id"]
    print(color("green", f" done ({elapsed:.1f}s)"))
    print(f"  video_id={video_id}  job_id={resp['job_id']}")
    print(f"  Polling status every 2s …\n")

    # Poll until done
    while True:
        time.sleep(2)
        s = requests.get(f"{args.api_url}/videos/{video_id}/status", headers=hdrs, timeout=10)
        if s.status_code == 200:
            st = s.json()
            status   = st["status"]
            pct      = st.get("percent", 0)
            total    = st.get("total_frames") or "?"
            processed = st.get("processed_frames") or 0

            status_col = {
                "pending":    "yellow",
                "processing": "cyan",
                "completed":  "green",
                "failed":     "red",
            }.get(status, "reset")

            print(
                f"  [{color(status_col, status):>12s}]  "
                f"frames {processed}/{total}  {pct:.1f}%",
                end="\r",
            )

            if status in ("completed", "failed"):
                print()
                if status == "completed":
                    print(f"\n  {color('green', '✓')} Processing complete!  View analytics at /videos/{video_id}")
                else:
                    print(f"\n  {color('red', '✗')} Processing failed.")
                break
        else:
            print(f"  Poll error {s.status_code}", end="\r")

        time.sleep(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="EyeGila demo script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("mode", choices=["live", "cctv", "video", "all"],
                        help="Demo mode to run")

    parser.add_argument("--api-url",        default="http://localhost:8000",
                        help="Server base URL (default: http://localhost:8000)")
    parser.add_argument("--username",       default="admin")
    parser.add_argument("--password",       default="admin")
    parser.add_argument("--duration",       type=int,   default=60,
                        help="Seconds for live mode (default: 60)")
    parser.add_argument("--rate",           type=float, default=8,
                        help="Detections per second per camera in live mode (default: 8)")
    parser.add_argument("--file",           default=None,
                        help="Path to video file for video mode")
    parser.add_argument("--intersection-id", type=int, default=None,
                        help="Intersection to attach video / demo cameras to")

    args = parser.parse_args()

    print(color("bold", "\n  EyeGila Demo  ") + f"  [{args.mode}]")
    print(f"  API: {args.api_url}\n")

    if args.mode == "live":
        run_live(args)
    elif args.mode == "cctv":
        run_cctv(args)
    elif args.mode == "video":
        run_video(args)
    elif args.mode == "all":
        run_live(args)
        run_cctv(args)
        if args.file:
            run_video(args)
        else:
            print(color("yellow", "\n  Skipping video mode (--file not provided)"))

    print()


if __name__ == "__main__":
    main()

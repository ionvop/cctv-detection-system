from common.database import Base, SessionLocal, engine
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Set, Optional
from ultralytics import YOLO
from common import models
import threading
import argparse
import time
import os
import cv2
import numpy as np

HEARTBEAT_INTERVAL_SEC = 4
CLAIM_EXPIRY_SEC = 15
POLL_INTERVAL_SEC = 5

@dataclass
class TrackState:
    """
    Runtime state associated with a single tracked object.
    """
    track_id: int
    cls_name: str
    db_detection_id: Optional[int] = None
    regions_entered: Set[int] = field(default_factory=set)
    last_seen_ts: float = field(default_factory=time.time)


def main() -> None:
    PRUNE_INTERVAL_SEC = 10
    TRACK_MAX_AGE_SEC = 30
    FPS_SAMPLE_INTERVAL = 30

    parser = argparse.ArgumentParser()
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="admin")
    parser.add_argument("--port",    type=int, default=554)
    parser.add_argument("--channel", type=int, default=1)
    parser.add_argument("--subtype", action="store_true")
    
    # for debugging bruv
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Use local webcam (device 2) instead of RTSP",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open a window with boxes/tracks (works with RTSP; needs a GUI)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print YOLO per-frame detection summaries",
    )

    args = parser.parse_args()

    show_preview = args.debug or args.show

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    model = YOLO("yolov8s.pt")

    cctv, claim_version = claim_camera(db)
    cctv_id = cctv.id

    rtsp_url = resolve_rtsp_url(cctv, args)

    fps_ref = [0.0]
    heartbeat = HeartbeatThread(cctv_id=cctv_id, fps_ref=fps_ref)
    heartbeat.start()

    cap = open_stream(rtsp_url, args.debug)
    if not cap.isOpened():
        print(f"[worker cctv={cctv_id}] initial stream open failed, entering reconnect...")
        cap = reconnect_stream(rtsp_url, args.debug, db, cctv_id)

    regions = initialize_regions(db, cctv_id)

    track_states: dict[int, TrackState] = {}
    last_prune_ts = time.time()
    frame_count = 0
    fps_timer_start = time.time()

    try:
        while True:
            ret, frame = cap.read()

            if not ret:
                # close the broken connection and reinitialize the states for the next iteration, annoying ahh language
                # btw, the heartbeat thread still runs in the background here
                cap.release()
                cap = reconnect_stream(rtsp_url, args.debug, db, cctv_id)
                regions = initialize_regions(db, cctv_id)
                track_states.clear()
                continue

            frame_count += 1

            # check ownership of cctv every 100 frames with verify claim (claim_version column) to avoid the split brain issue
            if frame_count % 100 == 0:
                if not verify_claim(db, cctv_id, claim_version):
                    print(f"[worker cctv={cctv_id}] claim lost, exiting inference loop")
                    break

            if frame_count % FPS_SAMPLE_INTERVAL == 0:
                elapsed = time.time() - fps_timer_start
                fps_ref[0] = round(FPS_SAMPLE_INTERVAL / elapsed if elapsed > 0 else 0, 1)
                fps_timer_start = time.time()

            results = model.track(frame, persist=True, verbose=args.verbose)

            frame_h, frame_w = frame.shape[:2]

            # show gui with draw regions utility function to debug the detection in region functionality
            if show_preview:
                    display = results[0].plot()
                    display = draw_regions(display, regions, frame_w, frame_h)
                    cv2.imshow(f"cctv-{cctv_id}", display)

            
            for box in results[0].boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id   = int(box.cls[0])
                cls_name = model.names[cls_id]
                conf     = float(box.conf[0])
                track_id = int(box.id[0]) if box.id is not None else None

                if track_id is None:
                    continue

                process_detection(db, regions, track_states, track_id, cls_name,
                                  conf, (x1, y1, x2, y2), cctv_id,
                                  frame_w, frame_h)

            now = time.time()
            if now - last_prune_ts > PRUNE_INTERVAL_SEC:
                prune_tracks(track_states, max_age_seconds=TRACK_MAX_AGE_SEC)
                last_prune_ts = now

            if show_preview and cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        # clean up connections, gui windows, and background thread (heartbeat)
        heartbeat.stop()
        heartbeat.join(timeout=5)
        cap.release()
        if show_preview:
            cv2.destroyAllWindows()
        release_camera(db, cctv_id)
        db.close()



def initialize_regions(
    db: Session,
    cctv_id: int,
) -> list[dict[str, any]]:
    """
    Load polygonal regions for a given CCTV from the database.

    :param db: Active SQLAlchemy session.
    :param cctv_id: Identifier of the CCTV whose regions should be loaded.
    :return: List of region dictionaries with keys:
             ``id``, ``street_id``, and ``region_points`` (each point having
             ``id``, ``x``, and ``y``).
    """
    regions = []
    db_regions = db.query(models.Region).filter(models.Region.cctv_id == cctv_id).all()

    for db_region in db_regions:
        region = {
            "id": db_region.id,
            "street_id": db_region.street_id,
            "region_points": [],
        }
        for pt in db_region.region_points:
            region["region_points"].append({"id": pt.id, "x": pt.x, "y": pt.y})
        regions.append(region)

    return regions


def process_detection(
    db: Session,
    regions: list[dict],
    track_states: dict[int, TrackState],
    track_id: int,
    cls_name: str,
    confidence: float,
    bounding_box: tuple[float, float, float, float],
    cctv_id: int,
    frame_w: int,
    frame_h: int,
) -> None:
    """
    Handle a single detection/tracking result for the current frame.

    :param db: Active SQLAlchemy session.
    :param regions: List of region dictionaries as returned by
                    :func:`initialize_regions`.
    :param track_states: Mapping of track IDs to their current
                         :class:`TrackState`.
    :param track_id: Identifier of the tracked object assigned by YOLO.
    :param cls_name: Human-readable class name predicted by the model.
    :param confidence: Detection confidence score (0–1).
    :param bounding_box: Tuple ``(x1, y1, x2, y2)`` in pixel coordinates.
    :param cctv_id: Identifier of the CCTV that produced this frame.
    :param frame_w: Frame width in pixels (used to normalize coordinates).
    :param frame_h: Frame height in pixels (used to normalize coordinates).
    """
    x1, y1, x2, y2 = bounding_box

    cx = ((x1 + x2) / 2) / frame_w
    cy = ((y1 + y2) / 2) / frame_h
    center = (cx, cy)

    if track_id not in track_states:
        track_states[track_id] = TrackState(track_id=track_id, cls_name=cls_name)

    state = track_states[track_id]
    state.last_seen_ts = time.time()
        
    if state.db_detection_id is None:
        matching_regions = [
            r for r in regions
            if is_point_in_polygon(center, [(p["x"], p["y"]) for p in r["region_points"]])
        ]
        if not matching_regions:
            return  

        detection = models.Detection(
            cctv_id=cctv_id,
            track_id=track_id,
            object_type=cls_name,
            confidence=round(confidence, 4),
            x1=round(x1 / frame_w, 4),
            y1=round(y1 / frame_h, 4),
            x2=round(x2 / frame_w, 4),
            y2=round(y2 / frame_h, 4),
        )
        db.add(detection)
        db.commit()
        db.refresh(detection)
        state.db_detection_id = detection.id

        for region in matching_regions:
            state.regions_entered.add(region["id"])
            db.add(models.DetectionInRegion(
                region_id=region["id"],
                detection_id=state.db_detection_id,
            ))
        db.commit()
        return

    new_entries = False
    for region in regions:
        region_id = region["id"]
        polygon = [(p["x"], p["y"]) for p in region["region_points"]]
        if is_point_in_polygon(center, polygon) and region_id not in state.regions_entered:
            state.regions_entered.add(region_id)
            db.add(models.DetectionInRegion(
                region_id=region_id,
                detection_id=state.db_detection_id,
            ))
            new_entries = True
    if new_entries:
        db.commit()


def prune_tracks(
    track_states: dict[int, TrackState],
    max_age_seconds: float,
) -> None:
    """
    Remove stale track states that have not been updated recently.

    :param track_states: Mapping of track IDs to :class:`TrackState`
                         instances. Entries are removed in-place.
    :param max_age_seconds: Maximum allowed age (in seconds) since a track
                            was last seen before it is discarded.
    """
    now = time.time()
    to_delete = [
        tid for tid, state in track_states.items()
        if now - state.last_seen_ts > max_age_seconds
    ]
    for tid in to_delete:
        del track_states[tid]


def get_center(
    bounding_box: tuple[int, int, int, int],
) -> tuple[float, float]:
    """
    Compute the center point of an axis-aligned bounding box.

    :param bounding_box: Tuple ``(x1, y1, x2, y2)`` in image coordinates.
    :return: Tuple ``(cx, cy)`` representing the center of the box.
    """
    x1, y1, x2, y2 = bounding_box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def is_point_in_polygon(
    point: tuple[float, float],
    polygon: list[tuple[float, float]],
) -> bool:
    """
    Determine if a point is inside a polygon using the ray casting algorithm.

    :param point: Tuple ``(x, y)``.
    :param polygon: List of ``(x, y)`` tuples defining the polygon vertices.
    :return: True if inside, False if outside.
    """
    if len(polygon) < 3:
        return False

    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_intersect:
                inside = not inside
    return inside


if __name__ == "__main__":
    main()

def draw_regions(
    frame,
    regions: list[dict],
    frame_w: int,
    frame_h: int,
):
    """
    Draw loaded region polygons onto the frame for visual verification.
    Points are stored normalized (0-1) so they are scaled back to pixels.
    """
    colors = [
        (0, 255, 0),    # green
        (255, 0, 0),    # blue
        (0, 165, 255),  # orange
        (0, 0, 255),    # red
        (255, 0, 255),  # magenta
    ]

    for i, region in enumerate(regions):
        color = colors[i % len(colors)]
        points = region["region_points"]

        if len(points) < 3:
            continue

        # scale normalized coords back to pixel coords
        pixel_points = [
            (int(p["x"] * frame_w), int(p["y"] * frame_h))
            for p in points
        ]

        pts = np.array(pixel_points, dtype=np.int32)
        cv2.polylines(frame, [pts], isClosed=True, color=color, thickness=2)

        # label with street_id in the center of the polygon
        cx = int(sum(p[0] for p in pixel_points) / len(pixel_points))
        cy = int(sum(p[1] for p in pixel_points) / len(pixel_points))
        cv2.putText(frame, f"region {region['id']} (street {region['street_id']})",
                    (cx, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    return frame

def claim_camera(db: Session) -> tuple[models.CCTV, int]:
    """
    Atomically claim an unclaimed or abandoned camera.

    Uses SELECT FOR UPDATE SKIP LOCKED on a subquery so the lock is
    unambiguous. The claim_version fencing token is incremented on every claim, so
    that a slow-but-alive worker can detect it lost its claim before
    writing duplicate detections.

    Blocks indefinitely, polling every POLL_INTERVAL_SEC until a camera
    becomes available.

    :return: (cctv row, claim_version) tuple.
    """
    
    worker_pid = os.getpid()
    print(f"[worker pid={worker_pid}] scanning for unclaimed camera...")

    while True:
        try:
            db.execute(text("BEGIN"))
            
            count = db.execute(text("SELECT COUNT(*) FROM cctvs")).scalar()
            if count == 0:
                print(f"[worker pid={worker_pid}] no cameras in database at all - waiting...")
                time.sleep(POLL_INTERVAL_SEC)
                continue

            # check for available cctvs using the worker_heartbeats table
            result = db.execute(text("""
                SELECT id FROM cctvs
                WHERE id NOT IN (
                    SELECT cctv_id FROM worker_heartbeats
                    WHERE last_seen > NOW() - (:expiry * INTERVAL '1 second')
                )
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """), {"expiry": CLAIM_EXPIRY_SEC}).fetchone()
        
            # exponential backoff here 
            if result is None:
                db.execute(text("ROLLBACK"))
                print(f"[worker pid={worker_pid}] no camera available, "
                      f"retrying in {POLL_INTERVAL_SEC}s...")
                time.sleep(POLL_INTERVAL_SEC)
                continue

            cctv_id = result[0]

            # claim a cctv and update the worker_heartbeats
            row = db.execute(text("""
                INSERT INTO worker_heartbeats
                    (cctv_id, worker_pid, last_seen, claimed_at, claim_version, status)
                VALUES
                    (:cctv_id, :pid, NOW(), NOW(), 1, 'running')
                ON CONFLICT (cctv_id) DO UPDATE SET
                    worker_pid    = EXCLUDED.worker_pid,
                    last_seen     = NOW(),
                    claimed_at    = NOW(),
                    claim_version = worker_heartbeats.claim_version + 1,
                    status        = 'running'
                RETURNING claim_version
            """), {"cctv_id": cctv_id, "pid": worker_pid}).fetchone()

            claim_version = row[0]

            # update the status of cctvs TODO: might be redundant
            db.execute(text(
                "UPDATE cctvs SET status = 'active' WHERE id = :id"
            ), {"id": cctv_id})

            db.execute(text("COMMIT"))

        except Exception as e:
            print(f"[worker pid={worker_pid}] claim attempt failed: {e}")
            try:
                db.execute(text("ROLLBACK"))
            except Exception:
                pass
            time.sleep(POLL_INTERVAL_SEC)
            continue

        cctv = db.query(models.CCTV).filter(models.CCTV.id == cctv_id).first()
        print(f"[worker pid={worker_pid}] claimed camera id={cctv_id} "
              f"name='{cctv.name}' claim_version={claim_version}")
        return cctv, claim_version


class HeartbeatThread(threading.Thread):
    """
    Sends a heartbeat to the database every HEARTBEAT_INTERVAL_SEC.

    Runs as a background thread so it dies automatically when the main
    process exits and ot not block the inference loop.
    """

    def __init__(self, cctv_id: int, fps_ref: list):
        super().__init__(daemon=True)
        self._cctv_id = cctv_id
        self._fps_ref = fps_ref
        self._stop_event = threading.Event()

    def run(self):
        db = SessionLocal()
        try:
            while not self._stop_event.is_set():
                try:
                    db.execute(text("""
                        UPDATE worker_heartbeats
                        SET last_seen = NOW(),
                            frames_per_second = :fps
                        WHERE cctv_id = :cctv_id
                    """), {"fps": self._fps_ref[0], "cctv_id": self._cctv_id})
                    db.commit()
                except Exception as e:
                    print(f"[heartbeat cctv={self._cctv_id}] write failed: {e}")
                    try:
                        db.rollback()
                    except Exception:
                        pass
                    try:
                        db.close()
                    except Exception:
                        pass
                    db = SessionLocal()

                self._stop_event.wait(HEARTBEAT_INTERVAL_SEC)
        finally:
            db.close()

    def stop(self):
        self._stop_event.set()


def release_camera(db: Session, cctv_id: int) -> None:
    """
    Delete the heartbeat row and mark the camera offline on clean exit.
    Another worker can claim it immediately after.
    """
    try:
        db.execute(text(
            "DELETE FROM worker_heartbeats WHERE cctv_id = :id"
        ), {"id": cctv_id})
        db.execute(text(
            "UPDATE cctvs SET status = 'offline' WHERE id = :id"
        ), {"id": cctv_id})
        db.commit()
        print(f"[worker] released camera id={cctv_id}")
    except Exception as e:
        print(f"[worker] release failed: {e}")
        db.rollback()


def verify_claim(db: Session, cctv_id: int, expected_version: int) -> bool:
    """
    Return True if this worker still holds the claim for cctv_id.

    If another worker stole the claim while the database was slow,
    claim_version will have been incremented and this returns False.

    Returns True on transient database errors to avoid exiting the
    inference loop on a momentary hiccup.
    """
    try:
        row = db.execute(text(
            "SELECT claim_version FROM worker_heartbeats WHERE cctv_id = :id"
        ), {"id": cctv_id}).fetchone()
    except Exception as e:
        print(f"[worker] verify_claim failed: {e}")
        return True

    if row is None or row[0] != expected_version:
        print(f"[worker] lost claim on cctv={cctv_id} "
              f"(expected version {expected_version}, got {row[0] if row else 'none'})")
        return False

    return True


def resolve_rtsp_url(cctv: models.CCTV, args: argparse.Namespace) -> str | None:
    """
    If cctv.rtsp_url is a full RTSP URL (MediaMTX, etc.), use it as-is.
    Otherwise treat it as a Dahua-style host/IP and build the default path.
    Returns None when --debug (webcam instead of RTSP).
    """
    if args.debug:
        return None
    raw = (cctv.rtsp_url or "").strip()
    lower = raw.lower()
    if lower.startswith("rtsp://") or lower.startswith("rtsps://"):
        return raw
    return (
        f"rtsp://{args.username}:{args.password}@{raw}:{args.port}"
        f"/cam/realmonitor?channel={args.channel}&subtype={1 if args.subtype else 0}"
    )


def open_stream(rtsp_url: str | None, debug: bool) -> cv2.VideoCapture:
    source = 2 if debug else rtsp_url
    if source is None:
        raise ValueError("rtsp_url is None and debug mode is off")
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def reconnect_stream(
    rtsp_url: str | None,
    debug: bool,
    db: Session,
    cctv_id: int,
) -> cv2.VideoCapture:
    """
    Update camera status to reconnecting and retry the RTSP connection
    with exponential backoff. The heartbeat keeps running during this
    period so the claim stays alive.
    """
    try:
        db.execute(text(
            "UPDATE cctvs SET status = 'reconnecting' WHERE id = :id"
        ), {"id": cctv_id})
        db.execute(text(
            "UPDATE worker_heartbeats SET status = 'reconnecting' WHERE cctv_id = :id"
        ), {"id": cctv_id})
        db.commit()
    except Exception as e:
        print(f"[worker cctv={cctv_id}] failed to update reconnecting status: {e}")
        db.rollback()

    delay = 2
    attempt = 0
    while True:
        attempt += 1
        print(f"[worker cctv={cctv_id}] reconnect attempt {attempt}, waiting {delay}s...")
        time.sleep(delay)
        cap = open_stream(rtsp_url, debug)
        if cap.isOpened():
            print(f"[worker cctv={cctv_id}] reconnected")
            try:
                db.execute(text(
                    "UPDATE cctvs SET status = 'active' WHERE id = :id"
                ), {"id": cctv_id})
                db.execute(text(
                    "UPDATE worker_heartbeats SET status = 'running' WHERE cctv_id = :id"
                ), {"id": cctv_id})
                db.commit()
            except Exception as e:
                print(f"[worker cctv={cctv_id}] failed to update active status: {e}")
                db.rollback()
            return cap
        cap.release()
        delay = min(delay * 2, 60)

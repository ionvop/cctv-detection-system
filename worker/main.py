from common.models import CCTV, Region, Detection, DetectionInRegion
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
import redis as redis_lib
from worker.claim import claim_camera, release_camera, verify_claim

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis = redis_lib.from_url(REDIS_URL)
from worker.heartbeat import HeartbeatThread
from worker.stream import open_stream, reconnect_stream, resolve_rtsp_url


@dataclass
class TrackState:
    """
    Runtime state associated with a single tracked object.

    This structure stores bookkeeping information that lets the system
    relate a YOLO tracking ID to database records and to which polygonal
    regions have already been reported for that track.
    """
    track_id: int
    cls_name: str
    db_detection_id: Optional[int] = None
    regions_entered: Set[int] = field(default_factory=set)
    last_seen_ts: float = field(default_factory=time.time)

PRUNE_INTERVAL_SEC = 10
TRACK_MAX_AGE_SEC = 30
FPS_SAMPLE_INTERVAL = 30
FLUSH_INTERVAL_SEC = 0.3
MAX_BUFFER_SIZE = 1000

def main() -> None:

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
    model = YOLO("eyegila_v3.pt")
    
    dir_buffer: list = []
    last_flush_ts = time.time()
    
    while True:
        cctv, claim_version = claim_camera(db)
        cctv_id: int = cctv.id # type: ignore
        rtsp_url = resolve_rtsp_url(cctv, args)
        
        fps_ref = [0.0]
        heartbeat = HeartbeatThread(cctv_id=cctv_id, fps_ref=fps_ref)
        heartbeat.start()
        
        regions = initialize_regions(db, cctv_id)
        track_states: dict[int, TrackState] = {}
        
        last_prune_ts = time.time()
        frame_count = 0
        fps_timer_start = time.time()

        cap = open_stream(rtsp_url, args.debug)
        if not cap.isOpened():
            print(f"[worker cctv={cctv_id}] initial stream open failed, entering reconnect...")
            cap = reconnect_stream(rtsp_url, args.debug, db, cctv_id)
        
        claim_lost = False
        
        try:
            while True:
                
                ret, frame = cap.read()

                # Grab extra frames to drain the buffer when inference is slow,
                # keeping the displayed/processed frame as close to live as possible.
                for _ in range(2):
                    ok, fresh = cap.read()
                    if ok:
                        frame = fresh

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
                        claim_lost = True
                        break

                if frame_count % FPS_SAMPLE_INTERVAL == 0:
                    elapsed = time.time() - fps_timer_start
                    fps_ref[0] = round(FPS_SAMPLE_INTERVAL / elapsed if elapsed > 0 else 0, 1)
                    fps_timer_start = time.time()

                results = model.track(frame, persist=True, verbose=args.verbose)

                frame_h, frame_w = frame.shape[:2]

                # Publish detection boxes as JSON so camera_ws.py can overlay
                # them on its own smooth RTSP stream without any encoding here.
                try:
                    detections_payload = []
                    for box in results[0].boxes:  # type: ignore
                        if box.id is None:
                            continue
                        bx1, by1, bx2, by2 = box.xyxy[0].tolist()
                        detections_payload.append({
                            "track_id":    int(box.id[0]),
                            "object_type": model.names[int(box.cls[0])],
                            "confidence":  round(float(box.conf[0]), 3),
                            "x1": round(bx1 / frame_w, 4),
                            "y1": round(by1 / frame_h, 4),
                            "x2": round(bx2 / frame_w, 4),
                            "y2": round(by2 / frame_h, 4),
                        })
                    import json as _json
                    _redis.setex(f"cam:{cctv_id}:detections", 5, _json.dumps({
                        "ts":    time.time(),
                        "boxes": detections_payload,
                    }))
                except Exception:
                    pass

                if show_preview:
                    annotated = results[0].plot()
                    annotated = draw_regions(annotated, regions, frame_w, frame_h)
                    cv2.imshow(f"cctv-{cctv_id}", annotated)

                
                if not results:
                    continue

                for box in results[0].boxes: # type: ignore
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cls_id   = int(box.cls[0])
                    cls_name = model.names[cls_id]
                    conf     = float(box.conf[0])
                    track_id = int(box.id[0]) if box.id is not None else None

                    if track_id is None:
                        continue

                    process_detection(db, regions, track_states, track_id, cls_name,
                                    conf, (x1, y1, x2, y2), cctv_id,
                                    frame_w, frame_h, dir_buffer)

                now = time.time()

                if now - last_flush_ts >= FLUSH_INTERVAL_SEC:
                    flush_detection_buffer(db, dir_buffer)
                    last_flush_ts = now
                    
                if now - last_prune_ts >= PRUNE_INTERVAL_SEC:
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
            if not claim_lost:
                release_camera(db, cctv_id)
            
        if claim_lost:
            # re-enter the outer loop to claim a new camera
            continue

        # clean shutdown (q pressed or exception) - exit entirely
        break


def initialize_regions(
    db: Session,
    cctv_id: int,
) -> list[dict[str, any]]: # type: ignore
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
    dir_buffer: list,
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
        
        try:
            db.add(detection)
            db.flush()
        except Exception as e:
            print(f"[worker] detection write failed: {e}")
            db.rollback()
            return

        state.db_detection_id = int(detection.id) # type: ignore

        for region in matching_regions:
            state.regions_entered.add(region["id"])
            if len(dir_buffer) >= MAX_BUFFER_SIZE:
                dir_buffer.pop(0)
                print("[worker] buffer full, dropping oldest detection")
            dir_buffer.append({
                "region_id": region["id"],
                "detection_id": state.db_detection_id,
            })
        return

    new_entries = False
    for region in regions:
        region_id = region["id"]
        polygon = [(p["x"], p["y"]) for p in region["region_points"]]
        if is_point_in_polygon(center, polygon) and region_id not in state.regions_entered:
            state.regions_entered.add(region_id)
            # db.add(models.DetectionInRegion(
            #     region_id=region_id,
            #     detection_id=state.db_detection_id,
            # ))
            
            if len(dir_buffer) >= MAX_BUFFER_SIZE:
                dir_buffer.pop(0)  
                print("[worker] buffer full, dropping oldest detection")

            dir_buffer.append({
                "region_id": region_id,
                "detection_id": state.db_detection_id,
            })
            new_entries = True


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

def recover_session(db: Session) -> Session:
    """
    Roll back and close the broken session, return a fresh one.
    Call this after any OperationalError on the main session.
    """
    try:
        db.rollback()
    except Exception:
        pass
    try:
        db.close()
    except Exception:
        pass
    return SessionLocal()

def flush_detection_buffer(
    db: Session,
    dir_buffer: list,
) -> None:
    items = dir_buffer.copy()
    dir_buffer.clear()
    try:
        if items:
            db.bulk_insert_mappings(models.DetectionInRegion, items) # type: ignore
        db.commit()
    except Exception as e:
        db.rollback()
        # Retry row-by-row so one bad region_id doesn't drop everything
        bad_regions: set[int] = set()
        for item in items:
            try:
                db.execute(
                    text("INSERT INTO detections_in_regions (region_id, detection_id) VALUES (:r, :d)"),
                    {"r": item["region_id"], "d": item["detection_id"]},
                )
                db.commit()
            except Exception as row_err:
                db.rollback()
                bad_regions.add(item["region_id"])
        if bad_regions:
            print(f"[worker] skipped stale region_ids {bad_regions} — restart worker to reload regions")
        
if __name__ == "__main__":
    main()
from common.database import Base, SessionLocal, engine
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from typing import Set, Optional
from ultralytics import YOLO
from common import models
import argparse
import time
import cv2


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


def main() -> None:
    PRUNE_INTERVAL_SEC = 10
    TRACK_MAX_AGE_SEC = 30
    parser = argparse.ArgumentParser()
    parser.add_argument("--cctv", type=int, help="CCTV ID", default=1)
    parser.add_argument("--username", help="Username", default="admin")
    parser.add_argument("--password", help="Password", default="admin")
    parser.add_argument("--ip", help="IP address", default="244.178.44.111")
    parser.add_argument("--port", type=int, help="Port", default=554)
    parser.add_argument("--channel", type=int, help="Channel", default=1)
    parser.add_argument("--subtype", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    model = YOLO("yolov8s.pt")
    rtsp_url = f"rtsp://{args.username}:{args.password}@{args.ip}:{args.port}/cam/realmonitor?channel={args.channel}&subtype={1 if args.subtype else 0}"
    cap = cv2.VideoCapture(2 if args.debug else rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    regions = initialize_regions(db, args.cctv)
    track_states: dict[int, TrackState] = {}
    last_prune_ts = time.time()

    while True:
        ret, frame = cap.read()

        if not ret:
            continue

        results = model.track(frame, persist=True)
        cv2.imshow("frame", results[0].plot())

        for box in results[0].boxes:
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            track_id = int(box.id[0]) if box.id is not None else None

            if track_id is None:
                continue

            process_detection(db, regions, track_states, track_id, cls_name, (x1, y1, x2, y2), args.cctv)

        now = time.time()

        if now - last_prune_ts > PRUNE_INTERVAL_SEC:
            prune_tracks(track_states, max_age_seconds=TRACK_MAX_AGE_SEC)
            last_prune_ts = now

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    db.close()


def initialize_regions(
    db: Session,
    cctv_id: int
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
            "region_points": []
        }

        for db_region_point in db_region.region_points:
            region["region_points"].append({
                "id": db_region_point.id,
                "x": db_region_point.x,
                "y": db_region_point.y
            })

        regions.append(region)

    return regions


def process_detection(
    db: Session,
    regions: list[dict],
    track_states: dict[int, TrackState],
    track_id: int,
    cls_name: str,
    bounding_box: tuple[int, int, int, int],
    cctv_id: int
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
    :param bounding_box: Tuple ``(x1, y1, x2, y2)`` in image coordinates.
    :param cctv_id: Identifier of the CCTV that produced this frame.
    """
    x1, y1, x2, y2 = bounding_box
    center = get_center(bounding_box)

    if track_id not in track_states:
        track_states[track_id] = TrackState(track_id=track_id, cls_name=cls_name)
        
    state = track_states[track_id]
    state.last_seen_ts = time.time()

    if state.db_detection_id is None:
        detection = models.Detection(
            cctv_id=cctv_id,
            x=(x1 + x2) / 2,
            y=(y1 + y2) / 2,
            type=cls_name
        )

        db.add(detection)
        db.commit()
        db.refresh(detection)
        state.db_detection_id = detection.id
        print(f"New detection: id={detection.id} cctv={cctv_id} x={detection.x} y={detection.y} type={detection.type}")

    for region in regions:
        region_id = region["id"]
        polygon = [(p["x"], p["y"]) for p in region["region_points"]]

        if is_point_in_polygon(center, polygon):
            if region_id not in state.regions_entered:
                state.regions_entered.add(region_id)

                detection_in_region = models.DetectionInRegion(
                    region_id=region_id,
                    detection_id=state.db_detection_id
                )

                db.add(detection_in_region)
                db.commit()
                db.refresh(detection_in_region)
                print(f"New detection in region: id={detection_in_region.id} region={region_id} detection={state.db_detection_id}")


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
        track_id
        for track_id, state in track_states.items()
        if now - state.last_seen_ts > max_age_seconds
    ]

    for track_id in to_delete:
        del track_states[track_id]


def get_center(
    bounding_box: tuple[int, int, int, int]
) -> tuple[int, int]:
    """
    Compute the center point of an axis-aligned bounding box.

    :param bounding_box: Tuple ``(x1, y1, x2, y2)`` in image coordinates.
    :return: Tuple ``(cx, cy)`` representing the center of the box.
    """
    x1, y1, x2, y2 = bounding_box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def is_point_in_polygon(
    point: tuple[int, int],
    polygon: list[tuple[int, int]]
) -> bool:
    """
    Determine if a point is inside a polygon using the ray casting algorithm.

    :param point: tuple (x, y)
    :param polygon: list of tuples [(x1, y1), (x2, y2), ...]
    :return: True if inside, False if outside
    """
    x, y = point
    inside = False

    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        # Check if point is between y-coordinates of the edge
        if (y1 > y) != (y2 > y):
            # Compute intersection of edge with horizontal ray
            x_intersect = (x2 - x1) * (y - y1) / (y2 - y1) + x1

            if x < x_intersect:
                inside = not inside

    return inside


if __name__ == "__main__":
    main()
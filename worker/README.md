# CCTV Worker

This module runs a YOLOv8-based tracking worker that:

- Connects to a CCTV RTSP stream (or local webcam in debug mode).
- Runs object detection and tracking with Ultralytics YOLO.
- Maps tracked objects to polygonal regions defined in the database.
- Writes detections and detection–region relationships to the database via SQLAlchemy.

It is intended to be used together with the database models defined in `common/database.py` and `common/models.py`.

---

## Features

- RTSP stream ingestion (Hikvision-style URL) or local camera (`--debug`).
- Object detection & tracking with `ultralytics.YOLO` (`yolov8s.pt`).
- In-memory tracking state per YOLO `track_id`.
- Region lookup from DB for a given CCTV:
  - Regions defined by polygon vertices (`RegionPoint`).
- For each track:
  - A single `Detection` per track is created in DB.
  - For each region entered (first time only), a `DetectionInRegion` row is created.
- Automatic pruning of stale track states.

---

## Command-Line Usage

From the project root:

```bash
python -m worker.main [options]
```

### Arguments

| Argument      | Type    | Default           | Description                                      |
|--------------|---------|-------------------|--------------------------------------------------|
| `--cctv`     | int     | `1`               | CCTV ID used when writing detections to DB. |
| `--username` | str     | `admin`           | RTSP username.                                   |
| `--password` | str     | `admin`           | RTSP password.                                   |
| `--ip`       | str     | `244.178.44.111`  | Camera IP address.                               |
| `--port`     | int     | `554`             | RTSP port.                                       |
| `--channel`  | int     | `1`               | Camera channel.                                  |
| `--subtype`  | flag    | `False`           | If set, RTSP uses `subtype=1` (substream).       |
| `--debug`    | flag    | `False`           | If set, reads from local camera index `2`.       |

RTSP URL pattern:

```text
rtsp://<username>:<password>@<ip>:<port>/cam/realmonitor?channel=<channel>&subtype=<0 or 1>
```

If `--debug` is set, the worker uses `cv2.VideoCapture(2)` instead of RTSP.

---

## How It Works

### 1. Initialization

In `main()`:

1. Parse CLI arguments.
2. Ensure all DB tables exist:

   ```py
   Base.metadata.create_all(bind=engine)
   ```

3. Open a DB session: `db = SessionLocal()`.
4. Load YOLO model: `model = YOLO("yolov8s.pt")`.
5. Open video source (RTSP or camera).
6. Load regions for the selected CCTV:

   ```py
   regions = initialize_regions(db, args.cctv)
   ```

   Each region dict contains:

   ```py
   {
       "id": <region_id>,
       "street_id": <street_id>,
       "region_points": [
           {"id": <point_id>, "x": <int>, "y": <int>},
           ...
       ]
   }
   ```

7. Initialize an in-memory mapping: `track_states: dict[int, TrackState] = {}`.

### 2. Per-frame Processing Loop

For each frame:

1. Read frame from `cv2.VideoCapture`.
2. Run YOLO tracking:

   ```py
   results = model.track(frame, persist=True)
   ```

3. Display annotated frame:

   ```py
   cv2.imshow("frame", results[0].plot())
   ```

4. For each `box` in `results[0].boxes`:
   - Extract bounding box (`x1, y1, x2, y2`), class ID and name (`cls_name`), and `track_id`.
   - Skip boxes without tracking ID.
   - Call:

     ```py
     process_detection(
         db, regions, track_states,
         track_id=track_id,
         cls_name=cls_name,
         bounding_box=(x1, y1, x2, y2),
         cctv_id=args.cctv,
     )
     ```

5. Periodically prune stale tracks with `prune_tracks(...)`.
6. Exit and clean up when `q` is pressed.

---

## Core Functions

### `initialize_regions(db, cctv_id) -> list[dict]`

Loads regions and their polygon vertices from DB:

- Reads `Region` rows filtered by `cctv_id`.
- For each region, includes all associated `RegionPoint`s.
- Returns a list of dicts for fast in-memory access.

### `process_detection(...)`

Handles a single tracked object in the current frame:

1. Compute center of bounding box with `get_center(...)`.
2. If `track_id` not in `track_states`, create a new `TrackState`.
3. If this is the first time we see this track (no `db_detection_id` yet):
   - Create a `models.Detection` row (with center coordinates and `type=cls_name`).
   - Commit and store `detection.id` in `TrackState.db_detection_id`.
4. For each region:
   - Build polygon as `[(x, y), ...]`.
   - Check if center is inside using `is_point_in_polygon(center, polygon)`.
   - If inside and region not yet reported for this track:
     - Add region to `state.regions_entered`.
     - Create `models.DetectionInRegion(region_id=..., detection_id=...)`.
     - Commit.

### `prune_tracks(track_states, max_age_seconds)`

- Removes entries from `track_states` whose `last_seen_ts` is older than `max_age_seconds`.
- Keeps memory use bounded and prevents buildup of stale tracks.

### `get_center(bounding_box) -> (cx, cy)`

- Computes the center of `(x1, y1, x2, y2)` using simple averaging.

### `is_point_in_polygon(point, polygon) -> bool`

- Implements the ray-casting algorithm to determine whether `point` lies inside `polygon` (list of `(x, y)` vertices).

---

## Notes & Caveats

- Coordinates stored in DB (`Detection.x`, `Detection.y`, `RegionPoint.x`, `RegionPoint.y`) are in image pixel space.
- All DB writes are synchronous (`db.commit()` on each new detection/region entry). For high-throughput systems, consider batching or background workers.
- Ensure that the YOLO model file `yolov8s.pt` is available (downloaded via `ultralytics` or placed in the working directory).

---

## Disclaimer

This documentation was generated by ChatGPT but the entire codebase was mostly written by hand.
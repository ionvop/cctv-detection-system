import asyncio
import json
import os
import queue as stdlib_queue
import threading
import time

import cv2
import numpy as np
import redis as redis_lib
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from common.database import SessionLocal
from common import models

router = APIRouter(prefix="/cctvs", tags=["Camera WebSocket"])

_TARGET_FPS = 15
_FRAME_INTERVAL = 1.0 / _TARGET_FPS
_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
_redis = redis_lib.from_url(_REDIS_URL)

_TYPE_COLORS: dict[str, tuple[int, int, int]] = {
    "car":        ( 22, 163,  74),
    "motorcycle": (  3, 105, 161),
    "tricycle":   (217, 119,   6),
    "truck":      (220,  38,  38),
    "pedicab":    (124,  58, 237),
    "pedestrian": (  8, 145, 178),
    "person":     (  8, 145, 178),
}
_DEFAULT_COLOR = (100, 100, 100)


def _draw_boxes(frame: np.ndarray, detections: list[dict]) -> None:
    h, w = frame.shape[:2]
    for det in detections:
        x1 = int(det["x1"] * w)
        y1 = int(det["y1"] * h)
        x2 = int(det["x2"] * w)
        y2 = int(det["y2"] * h)
        color = _TYPE_COLORS.get(det.get("object_type", ""), _DEFAULT_COLOR)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{det.get('object_type', '?')} {det.get('confidence', 0):.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        ty = max(y1 - 4, th + 2)
        cv2.rectangle(frame, (x1, ty - th - 2), (x1 + tw + 2, ty + 2), color, -1)
        cv2.putText(frame, label, (x1 + 1, ty),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)


def _enqueue(frame_q: stdlib_queue.Queue, data: bytes) -> None:
    if frame_q.full():
        try:
            frame_q.get_nowait()
        except stdlib_queue.Empty:
            pass
    try:
        frame_q.put_nowait(data)
    except stdlib_queue.Full:
        pass


_DELAY_SEC = 0.8       # seconds to hold frames before displaying
_MAX_DET_HISTORY = 120  # detection snapshots to keep (~2 min at 1/s inference)
_OUTPUT_WIDTH = 854     # resize before buffering to reduce memory usage


def _capture_thread(
    rtsp_url: str,
    cctv_id: int,
    frame_q: stdlib_queue.Queue,
    stop_event: threading.Event,
):
    """
    Delay-buffer approach: frames are held for _DELAY_SEC before being sent.
    Detection results (from the worker) are cached locally as they arrive.
    When a frame is released, we find the detection snapshot whose wall-clock
    timestamp is closest to that frame's capture time, guaranteeing boxes are
    always in sync with the video regardless of inference speed.
    """
    from collections import deque

    det_key = f"cam:{cctv_id}:detections"

    # (wall_time: float, frame: np.ndarray)  – raw frames waiting to be sent
    frame_buf: deque[tuple[float, np.ndarray]] = deque()

    # (det_ts: float, boxes: list)  – rolling history of detection snapshots
    det_history: deque[tuple[float, list]] = deque(maxlen=_MAX_DET_HISTORY)

    last_det_ts = 0.0
    last_read = 0.0

    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                cap.release()
                cap = cv2.VideoCapture(rtsp_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                continue

            mono_now = time.monotonic()
            wall_now = time.time()

            # Rate-limit intake to target FPS to keep buffer memory bounded
            if mono_now - last_read < _FRAME_INTERVAL:
                continue
            last_read = mono_now

            # Resize before buffering to reduce per-frame memory
            h, w = frame.shape[:2]
            if w > _OUTPUT_WIDTH:
                frame = cv2.resize(frame, (_OUTPUT_WIDTH, int(h * _OUTPUT_WIDTH / w)))

            frame_buf.append((wall_now, frame))

            # Absorb any new detection snapshot from Redis into local history
            raw = _redis.get(det_key)
            if raw:
                try:
                    data = json.loads(raw)
                    # Support both formats:
                    #   new: {"ts": <float>, "boxes": [...]}
                    #   old: [{box}, ...]
                    if isinstance(data, list):
                        boxes, det_ts = data, time.time()
                    else:
                        boxes, det_ts = data.get("boxes", []), data.get("ts", time.time())
                    if det_ts > last_det_ts:
                        det_history.append((det_ts, boxes))
                        last_det_ts = det_ts
                except Exception:
                    pass

            # Release frames that have waited long enough
            while frame_buf and wall_now - frame_buf[0][0] >= _DELAY_SEC:
                frame_ts, delayed_frame = frame_buf.popleft()

                # Find the detection snapshot closest in time to this frame
                best_boxes: list = []
                best_diff = float("inf")
                for det_ts, boxes in det_history:
                    diff = abs(det_ts - frame_ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_boxes = boxes

                if best_boxes:
                    _draw_boxes(delayed_frame, best_boxes)

                ok, jpeg = cv2.imencode(
                    ".jpg", delayed_frame, [cv2.IMWRITE_JPEG_QUALITY, 80]
                )
                if ok:
                    _enqueue(frame_q, jpeg.tobytes())
    finally:
        cap.release()


def _set_viewed(cctv_id: int, value: bool):
    db = SessionLocal()
    try:
        cctv = db.get(models.CCTV, cctv_id)
        if cctv:
            cctv.is_being_viewed = value
            db.commit()
    finally:
        db.close()


@router.websocket("/{cctv_id}/ws")
async def camera_ws(websocket: WebSocket, cctv_id: int):
    db = SessionLocal()
    try:
        cctv = db.get(models.CCTV, cctv_id)
        if not cctv:
            await websocket.close(code=4004)
            return
        rtsp_url = cctv.rtsp_url
        cctv.is_being_viewed = True
        db.commit()
    finally:
        db.close()

    await websocket.accept()

    frame_q: stdlib_queue.Queue = stdlib_queue.Queue(maxsize=2)
    stop_event = threading.Event()
    thread = threading.Thread(
        target=_capture_thread,
        args=(rtsp_url, cctv_id, frame_q, stop_event),
        daemon=True,
    )
    thread.start()

    try:
        while True:
            try:
                frame_bytes = await asyncio.to_thread(frame_q.get, True, 5.0)
            except Exception:
                break
            try:
                await websocket.send_bytes(frame_bytes)
            except (WebSocketDisconnect, RuntimeError):
                break
    finally:
        stop_event.set()
        _set_viewed(cctv_id, False)

# server/routers/mjpeg.py
import asyncio
import threading
import time
import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from common.database import SessionLocal, get_db
from common import models
from sqlalchemy.orm import Session
from typing import Annotated

router = APIRouter(prefix="/cctvs", tags=["MJPEG"])


def _capture_thread(rtsp_url: str, queue: asyncio.Queue, stop_event: threading.Event, loop: asyncio.AbstractEventLoop):
    """Reads frames from an RTSP stream in a background thread and puts them on the async queue."""
    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                # RTSP drop -wait briefly before retrying
                time.sleep(0.2)
                cap.release()
                cap = cv2.VideoCapture(rtsp_url)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                continue

            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 70]
            ok, jpeg = cv2.imencode('.jpg', frame, encode_params)
            if not ok:
                continue

            frame_bytes = jpeg.tobytes()

            # Non-blocking put -drop frame if consumer is slow
            try:
                asyncio.run_coroutine_threadsafe(
                    _put_nowait(queue, frame_bytes),
                    loop,
                ).result(timeout=0.05)
            except Exception:
                pass  # consumer too slow -drop this frame
    finally:
        cap.release()


async def _put_nowait(queue: asyncio.Queue, item: bytes):
    """Replace the oldest item if the queue is full so fresh frames always win."""
    if queue.full():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
    await queue.put(item)


def _set_viewed(cctv_id: int, value: bool):
    db = SessionLocal()
    try:
        cctv = db.get(models.CCTV, cctv_id)
        if cctv:
            cctv.is_being_viewed = value
            db.commit()
    finally:
        db.close()


@router.get("/{cctv_id}/stream")
async def mjpeg_stream(
    cctv_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """
    MJPEG stream for a camera. Sets is_being_viewed=True while connected.
    Streams ~20-30fps JPEG frames as multipart/x-mixed-replace.
    """
    cctv = db.get(models.CCTV, cctv_id)
    if not cctv:
        raise HTTPException(status_code=404, detail="Camera not found")

    rtsp_url = cctv.rtsp_url
    # Mark as being viewed
    cctv.is_being_viewed = True
    db.commit()
    db.close()

    queue: asyncio.Queue = asyncio.Queue(maxsize=4)
    stop_event = threading.Event()
    loop = asyncio.get_event_loop()

    thread = threading.Thread(
        target=_capture_thread,
        args=(rtsp_url, queue, stop_event, loop),
        daemon=True,
    )
    thread.start()

    async def frame_generator():
        try:
            consecutive_timeouts = 0
            while True:
                try:
                    frame_bytes = await asyncio.wait_for(queue.get(), timeout=3.0)
                    consecutive_timeouts = 0
                except asyncio.TimeoutError:
                    consecutive_timeouts += 1
                    if consecutive_timeouts >= 3:
                        # Stream dead after 9s of no frames
                        break
                    continue

                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n\r\n'
                    + frame_bytes
                    + b'\r\n'
                )
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            stop_event.set()
            _set_viewed(cctv_id, False)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )

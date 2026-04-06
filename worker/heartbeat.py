from common.database import SessionLocal
from sqlalchemy import text
import threading

HEARTBEAT_INTERVAL_SEC = 4

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

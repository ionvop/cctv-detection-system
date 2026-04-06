from sqlalchemy.orm import Session
from sqlalchemy import text
from common import models
import time
import os

CLAIM_EXPIRY_SEC = 15
POLL_INTERVAL_SEC = 5

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

            cctv_id: int = int(result[0])

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

            if row is None:
                db.execute(text("ROLLBACK"))
                print(f"[worker pid={worker_pid}] heartbeat insert returned nothing, retrying...")
                time.sleep(POLL_INTERVAL_SEC)
                continue

            claim_version: int = int(row[0])

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
        
        if cctv is None:
            raise RuntimeError(f"[worker pid={worker_pid}] claimed cctv_id={cctv_id} but row not found")
        
        print(f"[worker pid={worker_pid}] claimed camera id={cctv_id} "
              f"name='{cctv.name}' claim_version={claim_version}")
        return cctv, claim_version




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

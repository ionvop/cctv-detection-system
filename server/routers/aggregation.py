# server/routers/aggregation.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from common.database import SessionLocal
from common.models import AggregationSummary, Intersection
from sqlalchemy import text
import asyncio
import json

router = APIRouter(prefix="/aggregation", tags=["Aggregation"])

# holds all active SSE connections
connected_clients: list[asyncio.Queue] = []

async def aggregation_pusher():
    """Background task — queries aggregation_summaries every 5s and fans out to all clients."""
    while True:
        await asyncio.sleep(5)
        db = SessionLocal()
        try:
            rows = db.execute(text("""
                SELECT
                    a.intersection_id,
                    i.name  AS intersection_name,
                    a.street_id,
                    a.object_type,
                    a.window_start,
                    a.count
                FROM aggregation_summaries a
                JOIN intersections i ON i.id = a.intersection_id
                WHERE a.window_start = (
                    SELECT MAX(window_start)
                    FROM aggregation_summaries
                    WHERE intersection_id = a.intersection_id
                )
                ORDER BY a.intersection_id, a.street_id, a.object_type
            """)).fetchall()

            payload = json.dumps([
                {
                    "intersection_id": r.intersection_id,
                    "intersection_name": r.intersection_name,
                    "street_id": r.street_id,
                    "object_type": r.object_type,
                    "window_start": r.window_start.isoformat(),
                    "count": r.count,
                }
                for r in rows
            ])

            for queue in list(connected_clients):
                await queue.put(payload)

        except Exception as e:
            print(f"[SSE] aggregation query failed: {e}")
        finally:
            db.close()


@router.get("/stream")
async def stream_aggregation():
    queue: asyncio.Queue = asyncio.Queue()
    connected_clients.append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            connected_clients.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
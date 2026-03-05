from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from typing import Optional
import models
import schemas


router = APIRouter(
    prefix="/cctvs",
    tags=["CCTVs"]
)


@router.get("/{cctv_id}/detections", response_model=list[schemas.DetectionResponse])
def get_detections(
    cctv_id: int,
    start_time: int,
    end_time: int,
    region_start_x: Optional[float] = Query(None, ge=0, le=1),
    region_start_y: Optional[float] = Query(None, ge=0, le=1),
    region_end_x: Optional[float] = Query(None, ge=0, le=1),
    region_end_y: Optional[float] = Query(None, ge=0, le=1),
    db: Session = Depends(get_db)
):
    detections = (
        db.query(models.Detection)
        .filter(
            models.Detection.cctv_id == cctv_id,
            models.Detection.time >= start_time,
            models.Detection.time <= end_time
        )
        .all()
    )

    results = []

    for detection in detections:
        coords_query = db.query(models.Coord).filter(
            models.Coord.detection_id == detection.id
        )

        if None not in (
            region_start_x,
            region_start_y,
            region_end_x,
            region_end_y
        ):
            coords_query = coords_query.filter(
                models.Coord.x >= region_start_x,
                models.Coord.x <= region_end_x,
                models.Coord.y >= region_start_y,
                models.Coord.y <= region_end_y,
            )

        coords = coords_query.all()

        if not coords:
            continue

        results.append({
            "id": detection.id,
            "time": detection.time,
            "coords": [{"x": c.x, "y": c.y} for c in coords]
        })

    return results
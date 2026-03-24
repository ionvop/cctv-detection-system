from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from common.database import get_db
from typing import Optional
import common.models as models
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
    query = db.query(models.Detection).filter(
        models.Detection.cctv_id == cctv_id,
        models.Detection.time >= start_time,
        models.Detection.time <= end_time
    )

    # Apply region filter if provided
    if None not in (
        region_start_x,
        region_start_y,
        region_end_x,
        region_end_y
    ):
        query = query.filter(
            models.Detection.x >= region_start_x,
            models.Detection.x <= region_end_x,
            models.Detection.y >= region_start_y,
            models.Detection.y <= region_end_y,
        )

    return query.all()
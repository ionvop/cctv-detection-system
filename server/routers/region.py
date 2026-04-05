from server.schemas import RegionPointBase, RegionBase, RegionResponse
from server.utils import log_and_commit, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from common.models import User, Region, RegionPoint
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated


router = APIRouter(
    prefix="/regions",
    tags=["Regions"]
)


@router.post("/", response_model=RegionResponse)
def create_region(
    region: RegionBase,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> RegionResponse:
    db_region = Region(cctv_id=region.cctv_id, street_id=region.street_id)

    for region_point in region.region_points:
        db_region.region_points.append(RegionPoint(x=region_point.x, y=region_point.y))

    db.add(db_region)
    log_and_commit(f"User {user.username} created region {db_region.name}", db)
    db.refresh(db_region)
    return db_region
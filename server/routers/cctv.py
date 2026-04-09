from server.schemas import CCTVBase, CCTVCreate, CCTVUpdate, CCTVResponse
from server.utils import log_and_commit, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from common.models import User, CCTV
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated


router = APIRouter(
    prefix="/cctvs",
    tags=["CCTVs"]
)


@router.post("/", response_model=CCTVResponse)
def create_cctv(
    cctv: CCTVCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CCTVResponse:
    db_cctv = CCTV(name=cctv.name, intersection_id=cctv.intersection_id, rtsp_url=cctv.rtsp_url)
    db.add(db_cctv)
    log_and_commit(f"User {user.username} created cctv {db_cctv.name}", db)
    db.refresh(db_cctv)
    return db_cctv


@router.get("/", response_model=list[CCTVResponse])
def get_cctvs(
    db: Annotated[Session, Depends(get_db)],
) -> list[CCTVResponse]:
    return db.query(CCTV).all()


@router.get("/{cctv_id}", response_model=CCTVResponse)
def get_cctv(
    cctv_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> CCTVResponse:
    cctv = db.get(CCTV, cctv_id)

    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")
    
    return cctv


@router.put("/{cctv_id}", response_model=CCTVResponse)
def update_cctv(
    cctv_id: int,
    cctv: CCTVUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CCTVResponse:
    db_cctv = db.get(CCTV, cctv_id)

    if not db_cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")

    old_name = db_cctv.name
    message = f"User {user.username} updated cctv {old_name}"

    if cctv.name is not None:
        db_cctv.name = cctv.name
        message = f"User {user.username} updated cctv {old_name} to {db_cctv.name}"

    if cctv.rtsp_url is not None:
        db_cctv.rtsp_url = cctv.rtsp_url

    log_and_commit(message, db)
    db.refresh(db_cctv)
    return db_cctv


@router.delete("/{cctv_id}")
def delete_cctv(
    cctv_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    db_cctv = db.get(CCTV, cctv_id)

    if not db_cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")

    db.delete(db_cctv)
    log_and_commit(f"User {user.username} deleted cctv {db_cctv.name}", db)
    return {"detail": "CCTV deleted"}
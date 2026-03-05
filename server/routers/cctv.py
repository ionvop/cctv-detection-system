from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
import schemas


router = APIRouter(
    prefix="/cctvs",
    tags=["CCTVs"]
)


@router.post("/", response_model=schemas.CCTVResponse)
def create_cctv(cctv: schemas.CCTVCreate, db: Session = Depends(get_db)):
    db_cctv = models.CCTV(name=cctv.name)
    db.add(db_cctv)
    db.commit()
    db.refresh(db_cctv)
    return db_cctv


@router.get("/", response_model=list[schemas.CCTVResponse])
def get_cctvs(db: Session = Depends(get_db)):
    return db.query(models.CCTV).all()


@router.get("/{cctv_id}", response_model=schemas.CCTVResponse)
def get_cctv(cctv_id: int, db: Session = Depends(get_db)):
    cctv = db.query(models.CCTV).filter(models.CCTV.id == cctv_id).first()
    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")
    return cctv


@router.put("/{cctv_id}", response_model=schemas.CCTVResponse)
def update_cctv(cctv_id: int, update: schemas.CCTVUpdate, db: Session = Depends(get_db)):
    cctv = db.query(models.CCTV).filter(models.CCTV.id == cctv_id).first()
    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")

    if update.name is not None:
        cctv.name = update.name

    db.commit()
    db.refresh(cctv)
    return cctv


@router.delete("/{cctv_id}")
def delete_cctv(cctv_id: int, db: Session = Depends(get_db)):
    cctv = db.query(models.CCTV).filter(models.CCTV.id == cctv_id).first()
    if not cctv:
        raise HTTPException(status_code=404, detail="CCTV not found")

    db.delete(cctv)
    db.commit()
    return {"detail": "CCTV deleted"}

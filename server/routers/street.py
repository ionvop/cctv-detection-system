from server.schemas import StreetBase, StreetCreate, StreetUpdate, StreetResponse
from server.utils import log_and_commit, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from common.models import User, Street
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated


router = APIRouter(
    prefix="/streets",
    tags=["Streets"]
)


@router.post("/", response_model=StreetResponse)
def create_street(
    street: StreetCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StreetResponse:
    db_street = Street(intersection_id=street.intersection_id, name=street.name)
    db.add(db_street)
    log_and_commit(f"User {user.username} created street {db_street.name}", db)
    db.refresh(db_street)
    return db_street


@router.get("/", response_model=list[StreetResponse])
def get_streets(
    db: Annotated[Session, Depends(get_db)],
) -> list[StreetResponse]:
    return db.query(Street).all()


@router.get("/{street_id}", response_model=StreetResponse)
def get_street(
    street_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> StreetResponse:
    street = db.get(Street, street_id)

    if not street:
        raise HTTPException(status_code=404, detail="Street not found")
    
    return street


@router.put("/{street_id}", response_model=StreetResponse)
def update_street(
    street_id: int,
    street: StreetUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StreetResponse:
    db_street = db.get(Street, street_id)

    if not db_street:
        raise HTTPException(status_code=404, detail="Street not found")

    old_name = db_street.name
    db_street.name = street.name
    log_and_commit(f"User {user.username} updated street {old_name} to {db_street.name}", db)
    db.refresh(db_street)
    return db_street


@router.delete("/{street_id}")
def delete_street(
    street_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    db_street = db.get(Street, street_id)

    if not db_street:
        raise HTTPException(status_code=404, detail="Street not found")

    db.delete(db_street)
    log_and_commit(f"User {user.username} deleted street {db_street.name}", db)
    return {"detail": "Street deleted"}
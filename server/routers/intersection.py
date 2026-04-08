from server.schemas import IntersectionCreate, IntersectionUpdate, IntersectionResponse
from server.utils import log_and_commit, get_current_user
from fastapi import APIRouter, Depends, HTTPException
from common.models import User, Intersection
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated


router = APIRouter(
    prefix="/intersections",
    tags=["Intersections"]
)


@router.post("/", response_model=IntersectionResponse)
def create_intersection(
    intersection: IntersectionCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IntersectionResponse:
    db_intersection = Intersection(name=intersection.name, latitude=intersection.latitude, longitude=intersection.longitude)
    db.add(db_intersection)
    log_and_commit(f"User {user.username} created intersection {db_intersection.name}", db)
    db.refresh(db_intersection)
    return db_intersection


@router.get("/", response_model=list[IntersectionResponse])
def get_intersections(
    db: Annotated[Session, Depends(get_db)],
) -> list[IntersectionResponse]:
    return db.query(Intersection).all()


@router.get("/{intersection_id}", response_model=IntersectionResponse)
def get_intersection(
    intersection_id: int,
    db: Annotated[Session, Depends(get_db)],
) -> IntersectionResponse:
    intersection = db.get(Intersection, intersection_id)

    if not intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    
    return intersection


@router.put("/{intersection_id}", response_model=IntersectionResponse)
def update_intersection(
    intersection_id: int,
    intersection: IntersectionUpdate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> IntersectionResponse:
    db_intersection = db.get(Intersection, intersection_id)

    if not db_intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")
    
    message = f"User {user.username} updated intersection {db_intersection.name}"

    if intersection.name:
        old_name = db_intersection.name
        db_intersection.name = intersection.name
        message = f"User {user.username} updated intersection {old_name} to {db_intersection.name}"
    
    if intersection.latitude:
        db_intersection.latitude = intersection.latitude

    if intersection.longitude:
        db_intersection.longitude = intersection.longitude

    log_and_commit(message, db)
    db.refresh(db_intersection)
    return db_intersection


@router.delete("/{intersection_id}")
def delete_intersection(
    intersection_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    db_intersection = db.get(Intersection, intersection_id)

    if not db_intersection:
        raise HTTPException(status_code=404, detail="Intersection not found")

    db.delete(db_intersection)
    log_and_commit(f"User {user.username} deleted intersection {db_intersection.name}", db)
    return {"detail": "Intersection deleted"}
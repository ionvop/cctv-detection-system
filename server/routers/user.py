from server.schemas import UserCreate, UserUpdate, UserResponse
from server.utils import log_and_commit, require_superuser
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from common.database import get_db
from sqlalchemy.orm import Session
from bcrypt import hashpw, gensalt
from common.models import User
from typing import Annotated


router = APIRouter(
    prefix="/users",
    tags=["Users"],
    dependencies=[Depends(require_superuser)]
)


@router.post("/", response_model=UserResponse)
def create_user(
    user: UserCreate,
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    db_user = User(username=user.username, hash=hashpw(user.password.encode("utf-8"), gensalt()).decode("utf-8"))
    db.add(db_user)

    try:
        log_and_commit(f"User {user.username} created", db)
    except IntegrityError:
        raise HTTPException(status_code=400, detail="User already exists")

    db.refresh(db_user)
    return db_user


@router.get("/", response_model=list[UserResponse])
def get_users(
    db: Annotated[Session, Depends(get_db)]
) -> list[UserResponse]:
    return db.query(User).all()


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    user: UserUpdate,
    db: Annotated[Session, Depends(get_db)]
) -> UserResponse:
    db_user = db.query(User).filter(User.id == user_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.password is not None:
        db_user.hash = hashpw(user.password.encode("utf-8"), gensalt()).decode("utf-8")

    log_and_commit(f"User {db_user.username} updated", db)
    db.refresh(db_user)
    return db_user


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
) -> dict[str, str]:
    db_user = db.query(User).filter(User.id == user_id).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(db_user)
    log_and_commit(f"User {db_user.username} deleted", db)
    return {"detail": "User deleted"}
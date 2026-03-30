from fastapi import APIRouter, Depends, HTTPException
from common.models import User
from server.utils import log_and_commit, get_current_user
from server.schemas import UserBase
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated
from bcrypt import checkpw
from os import urandom


router = APIRouter(
    prefix="/login",
    tags=["Login"]
)


@router.post("/")
def login(
    user: UserBase,
    db: Session = Depends(get_db)
) -> dict[str, str]:
    db_user = db.get(User, user.username)

    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not checkpw(user.password.encode("utf-8"), db_user.hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = urandom(32).hex()
    db_user.session = token
    log_and_commit(f"User {db_user.username} logged in", db)
    return {"token": token}


# logout
@router.delete("/")
def logout(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, str]:
    user.session = None
    log_and_commit(f"User {user.username} logged out", db)
    return {"detail": "Logged out"}
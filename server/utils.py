from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from common.models import User, UserSession, Log
from fastapi import Depends, HTTPException
from common.database import get_db
from sqlalchemy.orm import Session
from typing import Annotated
from os import getenv


SESSION_EXPIRATION = 86400
SUPER_KEY = getenv("SUPER_KEY")
bearer_scheme = HTTPBearer()


def get_bearer_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]
) -> str:
    return credentials.credentials


def require_superuser(
    token: Annotated[str, Depends(get_bearer_token)]
) -> None:
    if not SUPER_KEY:
        raise HTTPException(status_code=500, detail="Superuser key not set")

    if token != SUPER_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_current_user(
    token: Annotated[str, Depends(get_bearer_token)],
    db: Annotated[Session, Depends(get_db)]
) -> User:
    db_user = db.query(User).join(UserSession, User.id == UserSession.user_id).filter(UserSession.token == token).first()

    if not db_user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    return db_user


def log_and_commit(
    message: str,
    db: Session
) -> None:
    db_log = Log(message=message)
    db.add(db_log)
    db.commit()
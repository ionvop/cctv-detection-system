from common.database import engine, Base, SessionLocal
from datetime import datetime, timedelta, timezone
from routers import user, login, intersection
from fastapi_utils.tasks import repeat_every
from server.utils import SESSION_EXPIRATION
from contextlib import asynccontextmanager
from common.models import UserSession
from fastapi import FastAPI
from dotenv import load_dotenv


@repeat_every(seconds=3600)
async def delete_expired_sessions() -> None:
    db = SessionLocal()
    db.query(UserSession).filter(UserSession.time < datetime.now(timezone.utc) - timedelta(seconds=SESSION_EXPIRATION)).delete()
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await delete_expired_sessions()
    yield


load_dotenv()
app = FastAPI(lifespan=lifespan)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
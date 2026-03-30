from common.database import engine, Base, SessionLocal
from server.routers import user, login, intersection
from datetime import datetime, timedelta, timezone
from fastapi_utils.tasks import repeat_every
from server.utils import SESSION_EXPIRATION
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


load_dotenv()
app = FastAPI(lifespan=lifespan)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
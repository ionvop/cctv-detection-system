from common.database import engine, Base, SessionLocal
from server.routers import user, login, intersection
from datetime import datetime, timedelta, timezone
from fastapi_utils.tasks import repeat_every
from server.utils import SESSION_EXPIRATION
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
from server.routers.aggregation import router as aggregation_router, aggregation_pusher
import asyncio

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    task = asyncio.create_task(aggregation_pusher())
    yield
    task.cancel()

load_dotenv()
app = FastAPI(lifespan=lifespan)
app.include_router(aggregation_router)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)

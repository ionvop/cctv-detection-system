from fastapi import FastAPI
from contextlib import asynccontextmanager
from common.database import engine, Base
from .routers import cctv
import common.models


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(cctv.router)
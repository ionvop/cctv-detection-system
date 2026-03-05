from fastapi import FastAPI
from contextlib import asynccontextmanager
from database import engine, Base
from routers import cctv


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(cctv.router)
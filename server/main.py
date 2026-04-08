from server.routers import user, login, intersection, street, cctv, detection, region
from contextlib import asynccontextmanager
from common.database import engine, Base
from dotenv import load_dotenv
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


load_dotenv()
app = FastAPI(lifespan=lifespan)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
app.include_router(street.router)
app.include_router(cctv.router)
app.include_router(detection.router)
app.include_router(region.router)
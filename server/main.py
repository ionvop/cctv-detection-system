from contextlib import asynccontextmanager
import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from common.database import engine, Base
from server.routers.aggregation import router as aggregation_router, aggregation_pusher
from server.routers.videos import router as videos_router
from server.routers.recommendations import router as recommendations_router
from server.routers.mjpeg import router as mjpeg_router
from server.routers.camera_ws import router as camera_ws_router
from server.routers import user, login, intersection, street, cctv, detection, region

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    task = asyncio.create_task(aggregation_pusher())
    yield
    task.cancel()


app = FastAPI(lifespan=lifespan)

# Allow the Vite dev server and any production origin to call the API directly
# (needed for SSE EventSource and WebSocket which browsers send with Origin headers)
_CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=r"http://localhost:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(aggregation_router)
app.include_router(recommendations_router)
app.include_router(mjpeg_router)
app.include_router(camera_ws_router)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
app.include_router(videos_router)
app.include_router(street.router)
app.include_router(cctv.router)
app.include_router(detection.router)
app.include_router(region.router)

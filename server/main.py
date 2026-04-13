<<<<<<< HEAD
from common.database import engine, Base
from server.routers import user, login, intersection
from server.routers.aggregation import router as aggregation_router, aggregation_pusher
from server.routers.videos import router as videos_router
from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
=======
from server.routers import user, login, intersection, street, cctv, detection, region
from contextlib import asynccontextmanager
from common.database import engine, Base
from dotenv import load_dotenv
from fastapi import FastAPI
>>>>>>> main


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    task = asyncio.create_task(aggregation_pusher())
    yield
    task.cancel()


load_dotenv()
app = FastAPI(lifespan=lifespan)
<<<<<<< HEAD

app.include_router(aggregation_router)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
app.include_router(videos_router)
=======
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
app.include_router(street.router)
app.include_router(cctv.router)
app.include_router(detection.router)
app.include_router(region.router)
>>>>>>> main

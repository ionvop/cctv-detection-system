from common.database import engine, Base, SessionLocal
from datetime import datetime, timedelta, timezone
from routers import user, login, intersection
from fastapi_utils.tasks import repeat_every
from server.utils import SESSION_EXPIRATION
from contextlib import asynccontextmanager
from common.models import UserSession
from fastapi import FastAPI


@repeat_every(seconds=3600)
async def delete_expired_sessions() -> None:
    db = SessionLocal()
    db.query(UserSession).filter(UserSession.time < datetime.now(timezone.utc) - timedelta(seconds=SESSION_EXPIRATION)).delete()
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    await delete_expired_sessions()

    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb;"))

        conn.execute(text("""
            SELECT create_hypertable(
                'detections', 'detected_at',
                chunk_time_interval => INTERVAL '1 hour',
                if_not_exists => TRUE
            );
        """))

        conn.execute(text("""
            SELECT add_retention_policy(
                'detections',
                INTERVAL '72 hours',
                if_not_exists => TRUE
            );
        """))

        conn.execute(text("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS aggregation_summaries
            WITH (timescaledb.continuous) AS
            SELECT
                intersection_id,
                time_bucket('1 minute', detected_at) AS window_start,
                object_type,
                COUNT(*) AS count
            FROM detections
            GROUP BY
                intersection_id,
                time_bucket('1 minute', detected_at),
                object_type
            WITH NO DATA;
        """))

        conn.execute(text("""
            SELECT add_continuous_aggregate_policy(
                'aggregation_summaries',
                start_offset => INTERVAL '2 minutes',
                end_offset => INTERVAL '1 minute',
                schedule_interval => INTERVAL '1 minute',
                if_not_exists => TRUE
            );
        """))

        conn.commit()

    yield

app = FastAPI(lifespan=lifespan)
app.include_router(user.router)
app.include_router(login.router)
app.include_router(intersection.router)
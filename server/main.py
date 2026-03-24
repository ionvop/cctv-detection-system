from sqlalchemy import text
from contextlib import asynccontextmanager
from common.database import engine, Base
import common.models

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

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
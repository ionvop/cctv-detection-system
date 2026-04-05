from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/traffic")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(Base.metadata, "before_create")
def skip_views(target, connection, **kw):
    tables = kw.get("tables")
    if tables is not None:
        tables[:] = [t for t in tables if not t.info.get("is_view")]


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

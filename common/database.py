from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine


DATABASE_URL = "mysql+mysqlconnector://root:@localhost:3306/_20260301"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    
    try:
        yield db
    finally:
        db.close()
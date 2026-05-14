from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    echo=False,
    connect_args={
        "connect_timeout": 10,
        "application_name": "dietly_backend",
    },
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        yield db
    finally:
        db.close()

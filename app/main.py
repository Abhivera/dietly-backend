import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine, text
from app.core.exception_handlers import register_exception_handlers
from app.core.schema_patch import apply_postgres_users_jwt_schema
from app.core.logging_config import configure_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.models import daily_steps, image, streaks, user, user_calories  # noqa: F401

logger = logging.getLogger(__name__)

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.schema_auto_create:
        Base.metadata.create_all(bind=engine)
        logger.info("schema_auto_create: ensured tables exist (SQLAlchemy create_all)")
    apply_postgres_users_jwt_schema(engine)
    yield


app = FastAPI(
    title="Dietly API",
    description="Food image analysis, meal tracking, and activity calories — JWT-authenticated API.",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)

register_exception_handlers(app)

Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
app.mount(
    "/media",
    StaticFiles(directory=settings.upload_dir),
    name="media",
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"message": "Dietly API is running", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health_check():
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception:
        logger.exception("DB health check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "detail": "Database is not reachable.",
                "message": "Database is not reachable.",
            },
        )

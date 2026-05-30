import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.database import get_database
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging
from app.db.tables import ensure_tables
from app.middleware.request_logging import RequestLoggingMiddleware

logger = logging.getLogger(__name__)

configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.schema_auto_create:
        ensure_tables()
        logger.info("schema_auto_create: ensured DynamoDB tables exist")
    yield


app = FastAPI(
    title="Calovia API",
    description="Food image analysis, meal tracking, and activity calories — Firebase-authenticated API.",
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
    return {"message": "Calovia API is running", "docs": "/docs"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health_check():
    try:
        db = get_database()
        db.users._table.meta.client.describe_table(
            TableName=db.users._table.name,
        )
        return {"status": "healthy", "database": "connected"}
    except Exception:
        logger.exception("DB health check failed")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "detail": "DynamoDB is not reachable.",
                "message": "DynamoDB is not reachable.",
            },
        )

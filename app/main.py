from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from app.routers import auth, users, chats, reports, companies, messages, integrations
from app.services.s3_service import s3_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager для FastAPI"""
    # Startup
    logger.info("🚀 Starting Pulse Backend...")

    # Проверяем подключение к S3
    from app.core.config import settings

    if settings.S3_ENDPOINT_URL:
        logger.info(f"🔗 Using custom S3 endpoint: {settings.S3_ENDPOINT_URL}")
    else:
        logger.info("🔗 Using AWS S3")

    s3_available = await s3_service.check_bucket_exists()
    if s3_available:
        logger.info(f"✅ S3 connection successful (bucket: {settings.S3_BUCKET_NAME})")
    else:
        logger.warning("⚠️ S3 connection failed - file uploads may not work")

    yield

    # Shutdown
    logger.info("📴 Shutting down Pulse Backend...")


app = FastAPI(
    title="Pulse Backend",
    description="AI-агент для анализа Яндекс.Метрики",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(chats.router)
app.include_router(messages.router)
app.include_router(reports.router)
app.include_router(companies.router)
app.include_router(integrations.router)


@app.get("/")
async def read_root():
    """
    Root endpoint to check if the API is running.
    """
    return {"message": "Pulse Backend is running"}

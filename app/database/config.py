from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.config import settings

# Create an asynchronous engine
async_engine = create_async_engine(settings.DATABASE_URL, echo=True)

# Create a session maker
SessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
)

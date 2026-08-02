from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
from app.db.models import Base

# Create async engine with fallback to aiosqlite for local testing if PostgreSQL is not available
database_url = settings.DATABASE_URL
if not database_url.startswith("postgresql+asyncpg") and not database_url.startswith("sqlite+aiosqlite"):
    # Convert standard postgresql:// to postgresql+asyncpg:// if needed
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    database_url,
    echo=False,
    future=True,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

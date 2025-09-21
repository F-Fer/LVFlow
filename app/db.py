import os
from typing import AsyncIterator
from sqlalchemy import text

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    user = os.getenv("POSTGRES_USER", "lvuser")
    password = os.getenv("POSTGRES_PASSWORD", "lvpass")
    db = os.getenv("POSTGRES_DB", "lvflow")
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"


engine: AsyncEngine = create_async_engine(get_database_url(), echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def ensure_schema() -> None:
    """Lightweight migration to ensure new columns exist without Alembic.

    Adds offer.pdf_filename if it doesn't exist.
    """
    async with engine.begin() as conn:
        # Postgres: check if column exists
        result = await conn.execute(
            text("SELECT 1 FROM information_schema.columns WHERE table_name='offer' AND column_name='pdf_filename'")
        )
        if result.scalar() is None:
            await conn.execute(text("ALTER TABLE offer ADD COLUMN pdf_filename varchar(255)"))


import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text


def get_database_url() -> str:
    """Normalize DATABASE_URL for asyncpg. Single source of truth."""
    raw = os.getenv("DATABASE_URL", "")
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw


DB_URL = get_database_url()

engine = create_async_engine(
    DB_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "prepared_statement_cache_size": 0,
        "statement_cache_size": 0,
    },
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def warm_pool():
    """Pre-create a DB connection at startup so the first request is fast."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
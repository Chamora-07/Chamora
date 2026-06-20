import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import update, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=1,
    max_overflow=2,
    pool_recycle=1800,
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def update_test_run(test_run_id: int, **kwargs):
    from db.models import TestRun

    async with async_session() as session:
        await session.execute(
            update(TestRun)
            .where(TestRun.id == test_run_id)
            .values(**kwargs)
        )
        await session.commit()
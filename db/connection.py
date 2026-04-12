import os 
from sqlalchemy.ext.asyncio import create_async_engine , async_sessionmaker
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv("DATABASE_URL", "").replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(DB_URL , pool_size=5 , max_overflow=10)

SessionLocal = async_sessionmaker(bind = engine, expire_on_commit=False)

async def get_db():
    async with SessionLocal() as session:
        yield session 
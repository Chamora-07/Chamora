import os
import asyncio
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from db.base import Base
from db.models import User, Application, Endpoint, Document, TestScript, TestRun , AnomalyDetectionConfig

load_dotenv()

async def init_models():
    """
    Scans the SQLAlchemy models and creates corresponding tables in Supabase.
    """
    raw_url = os.getenv("DATABASE_URL")
    
    if not raw_url:
        print("Error: DATABASE_URL not found in .env file!")
        return

    db_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(
        db_url, 
        poolclass=NullPool,
        echo=True  # need to change when it comes to production 
    )

    try:
        async with engine.begin() as conn:
            print("Scanning models and creating tables in Supabase...")
            await conn.run_sync(Base.metadata.create_all)
            print("Database schema initialized successfully!")
            
    except Exception as e:
        print(f"Initialization failed: {e}")
        
    finally:
        await engine.dispose()


async def ensure_ml_inference_need_column():
    """
    Backfills the `ml_inference_need` column when the database already exists.
    `create_all()` does not alter existing tables, so this keeps older deployments working.
    Reuses the shared engine to avoid creating a disposable connection.
    """
    from db.connection import engine

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "ALTER TABLE anomaly_detection_configs "
                "ADD COLUMN IF NOT EXISTS ml_inference_need BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        await conn.execute(
            text(
                "UPDATE anomaly_detection_configs "
                "SET ml_inference_need = FALSE "
                "WHERE ml_inference_need IS NULL"
            )
        )

if __name__ == "__main__":
    try:
        asyncio.run(init_models())
    except KeyboardInterrupt:
        print("\nProcess interrupted by user.")
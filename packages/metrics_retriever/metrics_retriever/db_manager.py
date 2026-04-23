import os
import logging
from sqlite3 import connect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from db.models import Endpoint, AnomalyDetectionConfig

logger = logging.getLogger(__name__)

class RetrieverDBManager:
    def __init__(self, db_url: str):
        """
        Initializes the async engine for Supabase.
        Ensures the URL uses the +asyncpg driver.
        """
        if not db_url:
            raise ValueError("DATABASE_URL is missing!")
            
        # Standardize the URL for asyncpg
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
        self.engine = create_async_engine(
            db_url, 
            echo=False,
            connect_args={
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            },
            pool_pre_ping=True
        )
        
        # Factory for creating async sessions
        self.AsyncSessionLocal = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def get_active_monitoring_jobs(self):
        """
        Performs a JOIN between anomaly_detection_configs and endpoints 
        to fetch everything the scraper needs to build PromQL queries.
        """
        async with self.AsyncSessionLocal() as session:
            try:
                # Build the query to join the settings with the container/probe names
                stmt = (
                    select(
                        AnomalyDetectionConfig.id.label("config_id"),
                        Endpoint.application_id,
                        Endpoint.id.label("endpoint_id"),
                        Endpoint.container_name,
                        Endpoint.target_name.label("probe_name")
                    )
                    .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
                    .where(AnomalyDetectionConfig.is_active == True)
                )
                
                result = await session.execute(stmt)
                
                # Convert the results into a list of dictionaries for the scraper
                # This makes it easy to access job['container_name'], etc.
                jobs = [dict(row._mapping) for row in result.all()]
                
                return jobs
                
            except Exception as e:
                logger.error(f"Failed to fetch active jobs from Supabase: {e}")
                return []
            finally:
                await session.close()

    async def close(self):
        """Cleanly close the database engine connection."""
        await self.engine.dispose()
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
from db.models import Endpoint, AnomalyDetectionConfig, Application  # <-- Add Application

logger = logging.getLogger(__name__)

class RetrieverDBManager:
    def __init__(self, db_url: str):
        if not db_url:
            raise ValueError("DATABASE_URL is missing!")
            
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
            
        self.engine = create_async_engine(
            db_url, 
            echo=False,
            connect_args={
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            },
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=3,
            pool_recycle=1800,
        )
        
        self.AsyncSessionLocal = sessionmaker(
            self.engine, 
            class_=AsyncSession, 
            expire_on_commit=False
        )

    async def get_active_monitoring_jobs(self):
        """
        Performs a 3-way JOIN:
          AnomalyDetectionConfig → Endpoint → Application
        to fetch the per-application victoria_metrics_url alongside
        the container/probe names needed for PromQL queries.
        """
        async with self.AsyncSessionLocal() as session:
            try:
                stmt = (
                    select(
                        AnomalyDetectionConfig.id.label("config_id"),
                        Endpoint.application_id,
                        Endpoint.id.label("endpoint_id"),
                        Endpoint.container_name,
                        Endpoint.target_name.label("probe_name"),
                        # ✅ Pull the per-app VM URL from the Application table
                        Application.victoria_metrics_url
                    )
                    .join(Endpoint, AnomalyDetectionConfig.endpoint_id == Endpoint.id)
                    # ✅ Second join to reach Application
                    .join(Application, Endpoint.application_id == Application.id)
                    .where(AnomalyDetectionConfig.is_active == True)
                    # ✅ Only include apps that actually have a VM URL configured
                    .where(Application.victoria_metrics_url.isnot(None))
                )
                
                result = await session.execute(stmt)
                jobs = [dict(row._mapping) for row in result.all()]
                
                if not jobs:
                    logger.warning(
                        "No active jobs found. Check that anomaly_detection_configs "
                        "is_active=True and applications have victoria_metrics_url set."
                    )
                
                return jobs
                
            except Exception as e:
                logger.error(f"Failed to fetch active jobs from Supabase: {e}")
                return []
            finally:
                await session.close()

    async def close(self):
        await self.engine.dispose()
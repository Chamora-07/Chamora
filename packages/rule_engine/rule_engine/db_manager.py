import time
from datetime import datetime, timezone 
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import AnomalyDetectionConfig, Anomaly
from .config import settings
import logging

logger = logging.getLogger("rule-engine.db")

class RuleDBManager:
    def __init__(self):
        self.engine = create_async_engine(
            settings.DATABASE_URL,
            connect_args={
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            }
        )
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)
        self._config_cache = {}  # {endpoint_id: (config_obj, expiry_time)}

    async def get_config(self, endpoint_id: int):
        """
        Fetches thresholds by endpoint_id (not application_id).
        Uses a 60-second cache to avoid hammering the DB.
        """
        now = time.time()
        if endpoint_id in self._config_cache:
            config, expiry = self._config_cache[endpoint_id]
            if now < expiry:
                return config

        async with self.Session() as session:
            stmt = select(AnomalyDetectionConfig).where(
                AnomalyDetectionConfig.endpoint_id == endpoint_id,  # ← correct field
                AnomalyDetectionConfig.is_active == True
            )
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config:
                self._config_cache[endpoint_id] = (config, now + 60)
            else:
                logger.warning(f"No active config found for endpoint_id={endpoint_id}")
            
            return config

    async def save_anomaly(self, v: dict):
        """Saves WARNING or CRITICAL window results to Supabase."""
        async with self.Session() as session:
            window_timestamp = datetime.fromtimestamp(v["timestamp"], tz=timezone.utc)
            
            new_anomaly = Anomaly(
                application_id=v["application_id"],
                config_id=v["config_id"],
                window_timestamp=window_timestamp,
                score=v["score"],
                severity=v["severity"],
                root_cause=v["root_cause"],
                evidence=v["evidence"]
            )
            session.add(new_anomaly)
            await session.commit()
            
            logger.info(
                f"Anomaly saved | app_id={v['application_id']} | "
                f"window_timestamp={window_timestamp.isoformat()} | "
                f"severity={v['severity']}"
            )
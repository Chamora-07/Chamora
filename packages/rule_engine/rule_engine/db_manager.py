import time
from datetime import datetime, timezone 
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from db.models import AnomalyDetectionConfig, Anomaly
from .config import settings

class RuleDBManager:
    def __init__(self):
        self.engine = create_async_engine(settings.DATABASE_URL , connect_args={
                "prepared_statement_cache_size": 0,
                "statement_cache_size": 0
            })
        self.Session = async_sessionmaker(bind=self.engine, expire_on_commit=False)
        self._config_cache = {} # {app_id: (config_obj, expiry_time)}

    async def get_config(self, app_id: int):
        """Fetches thresholds for a specific app with a 60-second cache."""
        now = time.time()
        if app_id in self._config_cache:
            config, expiry = self._config_cache[app_id]
            if now < expiry:
                return config

        async with self.Session() as session:
            stmt = select(AnomalyDetectionConfig).where(
                AnomalyDetectionConfig.endpoint_id == app_id, # Assuming 1:1 map
                AnomalyDetectionConfig.is_active == True
            )
            result = await session.execute(stmt)
            config = result.scalar_one_or_none()
            
            if config:
                self._config_cache[app_id] = (config, now + 60)
            return config

    async def save_anomaly(self, v: dict):
        """Saves WARNING or CRITICAL window results to Supabase."""
        async with self.Session() as session:
            dt_object = datetime.fromtimestamp(v["timestamp"], tz=timezone.utc)
            new_anomaly = Anomaly(
                application_id=v["application_id"],
                config_id=v["config_id"],
                window_timestamp=dt_object,
                score=v["score"],
                severity=v["severity"],
                root_cause=v["root_cause"],
                evidence=v["evidence"] # Stored as JSONB
            )
            session.add(new_anomaly)
            await session.commit()
import time
import logging
from datetime import datetime, timezone 
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, desc
from db.models import AnomalyDetectionConfig, Anomaly, MLModelMetric
from .config import settings

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
        self._ml_enabled_cache = {}  # {config_id: (is_enabled, expiry_time)}
        self._promoted_model_cache = {}  # {config_id: (model_obj, expiry_time)}
        self.ML_CACHE_TTL = 86400  # 24 hours in seconds
        self.PROMOTED_MODEL_CACHE_TTL = 300  # 5 minutes in seconds

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
                AnomalyDetectionConfig.endpoint_id == endpoint_id,
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
                # Note: verify if your Anomaly model uses root_cause or evidence
                # root_cause=v.get("root_cause"), 
                evidence=v["evidence"]
            )
            session.add(new_anomaly)
            await session.commit()
            
            logger.info(
                f"Anomaly saved | app_id={v['application_id']} | "
                f"window_timestamp={window_timestamp.isoformat()} | "
                f"severity={v['severity']}"
            )

    async def is_ml_inference_enabled(self, config_id: int) -> bool:
        """
        Checks the 'ml_inference_enabled' column in AnomalyDetectionConfig.
        Results are cached for 24 hours to prevent spamming the database.
        """
        now = time.time()
        
        # 1. Check local memory cache first
        if config_id in self._ml_enabled_cache:
            is_enabled, expiry = self._ml_enabled_cache[config_id]
            if now < expiry:
                return is_enabled

        # 2. Perform DB Refresh
        logger.info(f"🔄 [DB Refresh] Checking 'ml_inference_enabled' for Config {config_id}...")
        
        async with self.Session() as session:
            try:
                # Query specifically for the boolean flag
                stmt = select(AnomalyDetectionConfig.ml_inference_enabled).where(
                    AnomalyDetectionConfig.id == config_id
                )
                result = await session.execute(stmt)
                is_enabled = result.scalar()
                
                if is_enabled is None:
                    is_enabled = False 
                
                # Update 24-hour cache
                self._ml_enabled_cache[config_id] = (is_enabled, now + self.ML_CACHE_TTL)
                
                if is_enabled:
                    logger.warning(f"🤖 [Decision] ML is ENABLED for Config {config_id}. Suppressing rules for 24h.")
                else:
                    logger.info(f"📜 [Decision] ML is DISABLED for Config {config_id}. Rules remain active.")
                
                return is_enabled

            except Exception as e:
                # Error Cooldown: Cache 'False' for 5 mins to prevent loop spamming on DB/Attribute errors
                self._ml_enabled_cache[config_id] = (False, now + 300)
                logger.error(f"❌ [DB Error] Config {config_id}: {e}. Retrying in 5 minutes.")
                return False

    async def get_latest_promoted_ml_model(self, config_id: int):
        """
        Returns the latest promoted ML model metric row for a config.
        The newest record is selected by created_at, then by id as a tie-breaker.
        """
        now = time.time()

        if config_id in self._promoted_model_cache:
            model_row, expiry = self._promoted_model_cache[config_id]
            if now < expiry:
                return model_row

        logger.info(f"🔄 [DB Refresh] Checking latest promoted ML model for Config {config_id}...")

        async with self.Session() as session:
            try:
                stmt = (
                    select(MLModelMetric)
                    .where(
                        MLModelMetric.config_id == config_id,
                        MLModelMetric.is_promoted == True
                    )
                    .order_by(desc(MLModelMetric.created_at), desc(MLModelMetric.id))
                    .limit(1)
                )
                result = await session.execute(stmt)
                model_row = result.scalar_one_or_none()

                self._promoted_model_cache[config_id] = (model_row, now + self.PROMOTED_MODEL_CACHE_TTL)

                if model_row:
                    logger.warning(
                        f"🤖 [Decision] Promoted ML model found for Config {config_id}: "
                        f"version={model_row.model_version}, created_at={model_row.created_at}"
                    )
                else:
                    logger.info(f"📜 [Decision] No promoted ML model found for Config {config_id}. Rules remain active.")

                return model_row

            except Exception as e:
                self._promoted_model_cache[config_id] = (None, now + 300)
                logger.error(f"❌ [DB Error] Failed to read promoted ML model for Config {config_id}: {e}. Retrying in 5 minutes.")
                return None
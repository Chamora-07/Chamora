from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # --- Database Connectivity (The New Addition) ---
    # This is required for the RetrieverDBManager to poll Supabase
    database_url: str = Field(..., alias="DATABASE_URL")
    
    # --- Data Source (External VictoriaMetrics) ---
    vm_url: str = Field(..., alias="VM_URL")
    
    # --- Data Destination (Local Kafka in Docker) ---
    kafka_bootstrap_servers: str = Field("kafka:29092", alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic: str = Field("raw_metrics", alias="KAFKA_TOPIC")
    
    # --- Scraping Parameters ---
    # We keep this as a default, but it could also be moved to DB later
    scraping_interval: float = 1.0
    
    # NOTE: target_container_name and target_probe_name have been REMOVED.
    # These are now fetched dynamically from the database for every 'active_job'.

    class Config:
        env_file = ".env"
        extra = "ignore"
        populate_by_name = True # Allows both alias and field name usage

settings = Settings()
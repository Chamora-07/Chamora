from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Data Source (External VictoriaMetrics)
    vm_url: str = Field(..., alias="VM_URL")
    
    # Data Destination (Local Kafka in Docker)
    kafka_bootstrap_servers: str = Field("kafka:29092", alias="KAFKA_BOOTSTRAP_SERVERS")
    kafka_topic: str = Field("raw_metrics", alias="KAFKA_TOPIC")
    
    # Scraping Parameters
    scraping_interval: float = 1.0
    
    # Target details (Can be moved to a DB/Config later)
    target_container_name: str = "my_service"
    target_probe_name: str = "my_probe"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Kafka Connection
    kafka_bootstrap_servers: str = Field("kafka:29092", alias="KAFKA_BOOTSTRAP_SERVERS")
    
    # Topics
    # We read from where the retriever writes
    source_topic: str = Field("raw_metrics", alias="KAFKA_RAW_TOPIC")
    # We write to where the rule engine will read
    sink_topic: str = Field("processed_features", alias="KAFKA_FEATURE_TOPIC")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Kafka Connection (Using internal Docker network: kafka:29092)
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    KAFKA_CONSUMER_GROUP: str = os.getenv("KAFKA_CONSUMER_GROUP", "chamora-rule-engine-v1")
    
    # We use a specific variable for the Rule Engine's input topic
    KAFKA_TOPIC_FEATURES: str = os.getenv("KAFKA_TOPIC_FEATURES", "processed_features")

    # Supabase Connection String
    DATABASE_URL: str = os.getenv("DATABASE_URL")

settings = Settings()
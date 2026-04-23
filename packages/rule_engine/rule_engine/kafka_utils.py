from confluent_kafka import Consumer
import logging
from .config import settings

logger = logging.getLogger("rule-engine.kafka")

# 1. Define the Consumer Configuration
# These settings ensure we are reading in real-time and identifying as the 'Rule Engine'
kafka_config = {
    'bootstrap.servers': settings.KAFKA_BOOTSTRAP_SERVERS,
    'group.id': settings.KAFKA_CONSUMER_GROUP,
    'auto.offset.reset': 'latest',  # Start with the freshest data on restart
    'enable.auto.commit': True,     # Let Kafka handle offset tracking
}

# 2. Initialize the Consumer
# We create it once here so it can be imported as a singleton in main.py
try:
    consumer = Consumer(kafka_config)
    
    # 3. Subscribe to the 'processed_features' topic
    # This is the output of your Feature Builder stage
    consumer.subscribe([settings.KAFKA_TOPIC_FEATURES])
    
    logger.info(f"Subscribed to Kafka topic: {settings.KAFKA_TOPIC_FEATURES}")

except Exception as e:
    logger.error(f"Failed to initialize Kafka Consumer: {e}")
    raise e
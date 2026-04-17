import json
import logging
from confluent_kafka import Producer
from .config import settings

logger = logging.getLogger(__name__)

class KafkaManager:
    def __init__(self):
        conf = {
            'bootstrap.servers': settings.kafka_bootstrap_servers,
            'client.id': 'metrics-retriever-service',
            'linger.ms': 10,           # Small delay to batch messages for better throughput
            'compression.type': 'snappy',
            'acks': 1                  # Wait for lead broker to acknowledge
        }
        self.producer = Producer(conf)

    def delivery_report(self, err, msg):
        """
        Reports the success or failure of a message delivery.
        The key here is our application_id.
        """
        if err is not None:
            # Decode key for better error logging
            app_id = msg.key().decode('utf-8') if msg.key() else "Unknown"
            logger.error(f"Delivery failed for App ID {app_id}: {err}")
        else:
            # During development, we keep this to verify the 'Identity Thread'
            app_id = msg.key().decode('utf-8') if msg.key() else "Unknown"
            logger.info(
                f"App {app_id} metrics -> {msg.topic()} "
                f"partition [{msg.partition()}] @ offset {msg.offset()}"
            )

    def produce(self, key: str, data: dict):
        """
        Pushes a metric packet to Kafka.
        'key' MUST be the application_id (as a string).
        """
        try:
            # Ensure the key is a string for Kafka
            kafka_key = str(key).encode('utf-8')
            payload = json.dumps(data).encode('utf-8')
            
            self.producer.produce(
                settings.kafka_topic,
                key=kafka_key,
                value=payload,
                callback=self.delivery_report
            )
            
            # Serve delivery callbacks from previous produce calls
            self.producer.poll(0)
            
        except Exception as e:
            logger.error(f"Kafka Produce Error: {e}")

    def flush(self):
        """Used during shutdown to ensure all messages hit the broker."""
        logger.info("Flushing Kafka producer...")
        self.producer.flush(timeout=5)

# Global singleton
kafka_mgr = KafkaManager()
import os
import json
import asyncio
from confluent_kafka import Producer, KafkaException
from dotenv import load_dotenv

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC             = "load_test_jobs"


def _get_producer() -> Producer:
    return Producer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "acks":              "all",
        "retries":           3,
        "retry.backoff.ms":  500,
    })


async def publish_load_test_job(
    test_run_id:  int,
    storage_path: str,
    script_name:  str,
    app_id:       int,
    script_id:    int
):
    payload = {
        "test_run_id":  test_run_id,
        "storage_path": storage_path,
        "script_name":  script_name,
        "app_id":       app_id,
        "script_id":    script_id,
    }

    def _send():
        producer = _get_producer()

        def delivery_callback(err, msg):
            if err:
                raise KafkaException(f"Delivery failed: {err}")
            print(f"[Producer] Job {test_run_id} delivered to "
                  f"partition {msg.partition()} offset {msg.offset()}")

        producer.produce(
            topic=KAFKA_TOPIC,
            value=json.dumps(payload).encode("utf-8"),
            callback=delivery_callback
        )
        producer.flush()

    await asyncio.to_thread(_send)
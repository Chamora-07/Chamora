import os
import json
import asyncio
from confluent_kafka import Consumer, KafkaError, KafkaException
from dotenv import load_dotenv
from .executor import execute_k6_run

load_dotenv()

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
KAFKA_TOPIC          = "load_test_jobs"
KAFKA_CONSUMER_GROUP = "k6-worker-group"


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers":  KAFKA_BOOTSTRAP_SERVERS,
        "group.id":           KAFKA_CONSUMER_GROUP,
        "auto.offset.reset":  "earliest",
        "enable.auto.commit": False,
    })


async def start_consumer():
    consumer = _build_consumer()
    consumer.subscribe([KAFKA_TOPIC])
    print(f"[Consumer] Subscribed to topic: {KAFKA_TOPIC}")
    print(f"[Consumer] Consumer group: {KAFKA_CONSUMER_GROUP}")

    try:
        while True:
            msg = await asyncio.to_thread(consumer.poll, 1.0)

            if msg is None:
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                if msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    print("[Consumer] Topic not ready yet, retrying in 5s...")
                    await asyncio.sleep(5)
                    continue
                raise KafkaException(msg.error())

            try:
                job = json.loads(msg.value().decode("utf-8"))
            except json.JSONDecodeError as e:
                print(f"[Consumer] Bad message format, skipping: {e}")
                await asyncio.to_thread(consumer.commit, message=msg)
                continue

            print(f"[Consumer] Picked up job: test_run_id={job['test_run_id']}")

            try:
                await execute_k6_run(
                    test_run_id=job["test_run_id"],
                    storage_path=job["storage_path"],
                    script_name=job["script_name"],
                    app_id=job["app_id"],
                    script_id=job["script_id"]
                )
            except Exception as e:
                # Job failed but consumer keeps running for next job
                print(f"[Consumer] Job {job['test_run_id']} error: {e}")

            # Always commit — whether job succeeded or failed
            await asyncio.to_thread(consumer.commit, message=msg)
            print(f"[Consumer] Committed offset {msg.offset()} "
                  f"partition {msg.partition()}")

    except asyncio.CancelledError:
        print("[Consumer] Shutting down gracefully")
    except Exception as e:
        print(f"[Consumer] Fatal error: {e}")
        raise
    finally:
        consumer.close()
        print("[Consumer] Consumer closed")
"""Optional Redpanda producer for schema-validated test events."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from consumer import validate_event


def publish(broker: str, topic: str, event: dict) -> None:
    from kafka import KafkaProducer

    validate_event(event)
    producer = KafkaProducer(
        bootstrap_servers=broker,
        value_serializer=lambda value: json.dumps(value, ensure_ascii=False).encode("utf-8"),
    )
    try:
        producer.send(topic, event).get(timeout=15)
    finally:
        producer.flush()
        producer.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish one validated Data BI stream event.")
    parser.add_argument("event", type=Path, help="JSON file containing one event")
    parser.add_argument("--broker", default="localhost:19092")
    parser.add_argument("--topic", default="data-bi-events")
    args = parser.parse_args()
    publish(args.broker, args.topic, json.loads(args.event.read_text("utf-8")))


if __name__ == "__main__":
    main()

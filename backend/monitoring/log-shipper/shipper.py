"""日志转发器 — Docker logs → Elasticsearch (Windows/macOS/Linux 通用)

两种模式:
  模式 A (默认): Docker → log-shipper → Elasticsearch (直写)
  模式 B (生产):  Docker → log-shipper → Kafka → ES Consumer (Kafka 缓冲)
    启用: 设置 KAFKA_BOOTSTRAP_SERVERS=kafka:9092
"""
import json
import logging
import os
import time
import traceback

import docker
import httpx

logger = logging.getLogger("log-shipper")

ES_HOST = os.getenv("ES_HOST", "elasticsearch")
ES_PORT = int(os.getenv("ES_PORT", "9200"))
ES_URL = f"http://{ES_HOST}:{ES_PORT}"
INDEX_PREFIX = "shortdrama-logs"

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "")
KAFKA_TOPIC = os.getenv("KAFKA_LOG_TOPIC", "shortdrama-logs")

client = docker.from_env()

# ── Kafka producer (lazy init) ──
_kafka_producer = None


def _get_kafka_producer():
    """Lazy-init Kafka producer for log buffering."""
    global _kafka_producer
    if _kafka_producer is not None:
        return _kafka_producer
    try:
        from kafka import KafkaProducer
        _kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            compression_type="gzip",
            max_request_size=1048576,
            retries=3,
            acks=1,
        )
        logger.info("Kafka producer connected: %s", KAFKA_BOOTSTRAP)
    except ImportError:
        logger.warning("kafka-python not installed — falling back to ES direct")
        _kafka_producer = False  # Sentinel: tried and failed
    except Exception as e:
        logger.warning("Kafka connect failed: %s — falling back to ES direct", e)
        _kafka_producer = False
    return _kafka_producer


def send_to_kafka(entries: list):
    """Send log entries to Kafka topic (mode B)."""
    producer = _get_kafka_producer()
    if not producer:
        return False
    try:
        for entry in entries:
            producer.send(KAFKA_TOPIC, entry)
        producer.flush(timeout=5)
        logger.info("Shipped %d log entries to Kafka topic %s", len(entries), KAFKA_TOPIC)
        return True
    except Exception as e:
        logger.error("Kafka send failed: %s — falling back to ES", e)
        return False


def send_to_es(entries: list):
    """批量发送日志到 Elasticsearch (mode A)"""
    now = time.strftime("%Y.%m.%d")
    index = f"{INDEX_PREFIX}-{now}"
    # Build bulk payload
    body = ""
    for entry in entries:
        body += json.dumps({"index": {"_index": index}}) + "\n"
        body += json.dumps(entry, default=str) + "\n"

    try:
        resp = httpx.post(
            f"{ES_URL}/_bulk",
            content=body,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=10,
        )
        if resp.status_code >= 400:
            logger.warning("ES bulk insert failed: %s %s", resp.status_code, resp.text[:200])
        else:
            logger.info("Shipped %d log entries to %s", len(entries), index)
    except Exception as e:
        logger.error("ES connection failed: %s", e)


def collect_logs(since_ts: float, batch_size: int = 200):
    """Collect logs from all running containers since the given timestamp."""
    entries = []
    containers = client.containers.list()
    if not containers:
        return entries, time.time()

    max_ts = since_ts
    for container in containers:
        container_name = container.name.replace("shortdrama-", "")
        try:
            logs = container.logs(
                since=int(since_ts),
                timestamps=False,
                tail=50,
            ).decode("utf-8", errors="replace")
            for line in logs.strip().split("\n"):
                if not line:
                    continue
                ts = time.time()
                # Try to parse JSON log
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    data = {"message": line.strip()}
                data["container"] = container_name
                data["@timestamp"] = time.strftime(
                    "%Y-%m-%dT%H:%M:%S", time.gmtime(ts)) + "Z"
                entries.append(data)
            max_ts = time.time()
        except Exception as e:
            logger.debug("Failed to read logs from %s: %s", container_name, e)

    return entries, max_ts


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info("Log shipper started, target: %s", ES_URL)

    # Wait for ES to be ready
    for _ in range(30):
        try:
            r = httpx.get(f"{ES_URL}/_cluster/health", timeout=5)
            if r.status_code < 500:
                break
        except Exception:
            pass
        time.sleep(5)

    since_ts = time.time() - 10  # Start 10 seconds ago

    while True:
        try:
            entries, new_ts = collect_logs(since_ts, batch_size=200)
            if entries:
                # Mode B: Kafka if available, else ES direct
                if KAFKA_BOOTSTRAP:
                    sent = send_to_kafka(entries)
                    if not sent:
                        send_to_es(entries)  # Fallback to ES direct
                else:
                    send_to_es(entries)
            since_ts = new_ts
        except Exception:
            logger.error("Collect loop error: %s", traceback.format_exc())

        time.sleep(10)  # Poll every 10 seconds


if __name__ == "__main__":
    main()

"""日志转发器 — Docker logs → Elasticsearch (Windows/macOS/Linux 通用)"""
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

client = docker.from_env()


def send_to_es(entries: list):
    """批量发送日志到 Elasticsearch"""
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
                send_to_es(entries)
            since_ts = new_ts
        except Exception:
            logger.error("Collect loop error: %s", traceback.format_exc())

        time.sleep(10)  # Poll every 10 seconds


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""MySQL → Elasticsearch 数据同步脚本
将 cases 表全量/增量同步到 ES，支持定时执行或 Canal/Logstash 触发。
"""
import json
import logging
import os
import sys
import time
from datetime import datetime

import pymysql
from elasticsearch import Elasticsearch, helpers

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_cases")

# ---- 配置 ----
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "admin")
MYSQL_PASS = os.getenv("MYSQL_PASSWORD", "admin123")
MYSQL_DB   = os.getenv("MYSQL_DB", "shortdrama")

ES_HOST    = os.getenv("ES_HOST", "http://elasticsearch:9200")
ES_INDEX   = "cases"
BATCH_SIZE = 100


def get_mysql_conn():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASS,
        database=MYSQL_DB, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_cases(conn, last_sync: str = ""):
    """拉取案例数据，支持增量同步（基于 updated_at）"""
    sql = """SELECT id, title, description, author, cover_url, demo_video_url,
             genre, tags, status, view_count, like_count, share_count,
             user_id, created_at, updated_at
             FROM cases WHERE status = 'published'"""
    args = []
    if last_sync:
        sql += " AND updated_at > %s"
        args.append(last_sync)

    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def case_to_es_doc(row: dict) -> dict:
    """MySQL 行 → ES 文档"""
    tags = [t.strip() for t in row["tags"].split(",") if t.strip()] if row["tags"] else []
    return {
        "_index": ES_INDEX,
        "_id": row["id"],
        "_source": {
            "id": row["id"],
            "title": row["title"] or "",
            "description": row["description"] or "",
            "author": row["author"] or "",
            "tags": tags,
            "genre": row["genre"] or "",
            "view_count": int(row["view_count"] or 0),
            "like_count": int(row["like_count"] or 0),
            "share_count": int(row["share_count"] or 0),
            "status": row["status"] or "published",
            "cover_url": row["cover_url"] or "",
            "demo_video_url": row["demo_video_url"] or "",
            "user_id": row["user_id"] or "",
            "created_at": row["created_at"].isoformat() if isinstance(row["created_at"], datetime) else str(row["created_at"] or ""),
            "updated_at": row["updated_at"].isoformat() if isinstance(row["updated_at"], datetime) else str(row["updated_at"] or ""),
        },
    }


def sync_full(es: Elasticsearch):
    """全量同步"""
    conn = get_mysql_conn()
    try:
        rows = fetch_cases(conn)
        logger.info("全量同步: %d 条案例待索引", len(rows))

        actions = [case_to_es_doc(r) for r in rows]
        success, errors = helpers.bulk(es, actions, chunk_size=BATCH_SIZE, raise_on_error=False)
        logger.info("全量同步完成: success=%d, errors=%d", success, len(errors))
        if errors:
            for err in errors[:5]:
                logger.warning("ES bulk error: %s", err)
    finally:
        conn.close()


def sync_incremental(es: Elasticsearch, checkpoint_file="/tmp/es_sync_checkpoint"):
    """增量同步（基于 updated_at checkpoint）"""
    last_sync = ""
    if os.path.exists(checkpoint_file):
        with open(checkpoint_file) as f:
            last_sync = f.read().strip()

    conn = get_mysql_conn()
    try:
        rows = fetch_cases(conn, last_sync)
        if not rows:
            logger.info("增量同步: 无新数据")
            return

        logger.info("增量同步: %d 条案例待更新", len(rows))
        actions = [case_to_es_doc(r) for r in rows]
        success, errors = helpers.bulk(es, actions, chunk_size=BATCH_SIZE, raise_on_error=False)
        logger.info("增量同步完成: success=%d, errors=%d", success, len(errors))

        # 更新 checkpoint
        latest = max(r["updated_at"] for r in rows)
        with open(checkpoint_file, "w") as f:
            f.write(latest.isoformat() if isinstance(latest, datetime) else str(latest))
    finally:
        conn.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    es = Elasticsearch(ES_HOST)

    if not es.ping():
        logger.error("无法连接 Elasticsearch: %s", ES_HOST)
        sys.exit(1)

    if mode == "full":
        sync_full(es)
    elif mode == "incremental":
        sync_incremental(es)
    elif mode == "daemon":
        logger.info("启动增量同步守护进程 (间隔 30s)")
        while True:
            try:
                sync_incremental(es)
            except Exception as e:
                logger.error("同步异常: %s", e)
            time.sleep(30)
    else:
        logger.error("未知模式: %s (可选: full / incremental / daemon)", mode)
        sys.exit(1)

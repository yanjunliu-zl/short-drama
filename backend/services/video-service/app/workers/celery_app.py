from celery import Celery
import os

# 从环境变量获取配置
# P1: Use pyamqp:// for better RabbitMQ cluster support (heartbeat, confirm_publish)
broker_url = os.getenv("CELERY_BROKER_URL", "pyamqp://guest:guest@localhost:5672//")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/6")

# 创建Celery应用
celery_app = Celery(
    "video_worker",
    broker=broker_url,
    backend=result_backend,
    include=["app.workers.tasks"]
)

# 配置 — P1: HA-optimized for RabbitMQ cluster + quorum queues
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    # P1: Broker transport options for HA
    broker_transport_options={
        "confirm_publish": True,           # Wait for broker confirmation
        "max_retries": 5,                  # Retry on connection failure
        "interval_start": 0.5,             # Initial retry delay
        "interval_step": 0.5,              # Backoff step
        "interval_max": 3.0,               # Max retry delay
    },
    # P1: Priority queue support
    task_queue_max_priority=10,
    task_default_priority=5,
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.workers.tasks"])
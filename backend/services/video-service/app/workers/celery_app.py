from celery import Celery
import os

# 从环境变量获取配置
broker_url = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

# 创建Celery应用
celery_app = Celery(
    "video_worker",
    broker=broker_url,
    backend=result_backend,
    include=["app.workers.tasks"]
)

# 配置
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
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.workers.tasks"])
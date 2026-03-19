from app.workers.celery_app import celery_app
import time

@celery_app.task(bind=True)
def process_video(self, video_id: str):
    """处理视频任务 -  placeholder"""
    # 模拟长时间运行的任务
    self.update_state(state="PROGRESS", meta={"progress": 10})
    time.sleep(1)
    self.update_state(state="PROGRESS", meta={"progress": 50})
    time.sleep(1)
    self.update_state(state="PROGRESS", meta={"progress": 90})
    time.sleep(1)
    return {"video_id": video_id, "status": "processed", "progress": 100}
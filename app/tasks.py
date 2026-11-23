import time
from datetime import datetime, timedelta, timezone
import httpx
from app.database import SessionLocal
from app.models import MonitorJob
from app.worker import celery_app


@celery_app.task(name="app.tasks.check_url_task")
def check_url_task(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(MonitorJob).filter(MonitorJob.id == job_id).first()
        if not job:
            return {"error": "Job not found"}

        start_time = time.perf_counter()
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                response = client.get(job.target_url)

            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            job.status = "COMPLETED"
            job.http_status_code = response.status_code
            job.response_time_ms = elapsed_ms
            job.error_message = None
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            job.status = "FAILED"
            job.response_time_ms = elapsed_ms
            job.error_message = str(exc)

        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"job_id": job.id, "status": job.status}
    finally:
        db.close()


@celery_app.task(name="app.tasks.periodic_health_sweep")
def periodic_health_sweep():
    """مهمة دورية بيشغلها الـ Beat لإعادة فحص آخر 5 روابط"""
    db = SessionLocal()
    try:
        recent_urls = (
            db.query(MonitorJob.target_url)
            .distinct()
            .limit(5)
            .all()
        )
        triggered = 0
        for (url,) in recent_urls:
            new_job = MonitorJob(target_url=url, status="PENDING")
            db.add(new_job)
            db.commit()
            db.refresh(new_job)
            check_url_task.delay(new_job.id)
            triggered += 1
        return {"swept_urls": triggered}
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_jobs")
def cleanup_old_jobs():
    """مسح السجلات اللي مر عليها أكتر من 7 أيام"""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        deleted = db.query(MonitorJob).filter(MonitorJob.created_at < cutoff).delete()
        db.commit()
        return {"deleted_records": deleted}
    finally:
        db.close()
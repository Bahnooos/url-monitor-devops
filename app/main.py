from fastapi import Depends, FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, HttpUrl
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from app.config import settings
from app.database import get_db
from app.models import MonitorJob
from app.tasks import check_url_task

app = FastAPI(
    title="URL Monitor & Async Report Processor",
    docs_url="/docs" if settings.environment != "production" else None,
)

# تفعيل الـ Metrics لـ Prometheus تلقائياً على /metrics
Instrumentator().instrument(app).expose(app)


class JobCreateRequest(BaseModel):
    target_url: HttpUrl


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        r = redis.from_url(settings.redis_url)
        r.ping()
        return {"status": "healthy", "database": "up", "redis": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dependency unhealthy: {str(e)}")


@app.post("/jobs", status_code=202)
def create_monitor_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    job = MonitorJob(target_url=str(payload.target_url), status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)

    # إرسال المهمة لطابور Redis بدون تعطيل الـ Response
    check_url_task.delay(job.id)

    return {
        "job_id": job.id,
        "target_url": job.target_url,
        "status": job.status,
        "message": "Job queued successfully",
    }


@app.get("/jobs/{job_id}")
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(MonitorJob).filter(MonitorJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "target_url": job.target_url,
        "status": job.status,
        "http_status_code": job.http_status_code,
        "response_time_ms": job.response_time_ms,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
    }
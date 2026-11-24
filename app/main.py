from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, HttpUrl
from sqlalchemy import desc, text
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

Instrumentator().instrument(app).expose(app)


class JobCreateRequest(BaseModel):
    target_url: HttpUrl


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>URL Monitor Dashboard</title>
        <style>
            body { font-family: system-ui, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 20px; background: #0f172a; color: #e2e8f0; }
            h1 { color: #38bdf8; }
            .box { display: flex; gap: 10px; margin-bottom: 24px; }
            input { flex: 1; padding: 12px; border-radius: 6px; border: 1px solid #334155; background: #1e293b; color: #fff; font-size: 16px; }
            button { padding: 12px 24px; border-radius: 6px; border: none; background: #38bdf8; color: #0f172a; font-weight: bold; cursor: pointer; font-size: 16px; }
            button:hover { background: #0284c7; color: #fff; }
            table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }
            th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #334155; font-size: 14px; }
            th { background: #334155; color: #94a3b8; }
            .PENDING { color: #facc15; font-weight: bold; }
            .COMPLETED { color: #4ade80; font-weight: bold; }
            .FAILED { color: #f87171; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1>URL Monitor & Async Worker</h1>
        <div class="box">
            <input type="url" id="urlInput" placeholder="https://github.com" required />
            <button onclick="submitUrl()">Check URL</button>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Target URL</th>
                    <th>Status</th>
                    <th>HTTP Code</th>
                    <th>Latency (ms)</th>
                    <th>Job ID</th>
                </tr>
            </thead>
            <tbody id="jobsTable"></tbody>
        </table>

        <script>
            async function submitUrl() {
                const input = document.getElementById('urlInput');
                if (!input.value) return;
                await fetch('/jobs', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ target_url: input.value })
                });
                input.value = '';
                loadJobs();
            }

            async function loadJobs() {
                const res = await fetch('/jobs');
                const jobs = await res.json();
                const tbody = document.getElementById('jobsTable');
                tbody.innerHTML = jobs.map(j => `
                    <tr>
                        <td>${j.target_url}</td>
                        <td class="${j.status}">${j.status}</td>
                        <td>${j.http_status_code ?? '-'}</td>
                        <td>${j.response_time_ms ? j.response_time_ms + ' ms' : '-'}</td>
                        <td style="font-family: monospace; font-size: 12px;">${j.job_id.slice(0, 8)}...</td>
                    </tr>
                `).join('');
            }

            loadJobs();
            setInterval(loadJobs, 2000); // تحديث تلقائي كل ثانيتين
        </script>
    </body>
    </html>
    """


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        r = redis.from_url(settings.redis_url)
        r.ping()
        return {"status": "healthy", "database": "up", "redis": "up"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Dependency unhealthy: {str(e)}")


@app.get("/jobs")
def list_jobs(db: Session = Depends(get_db)):
    jobs = db.query(MonitorJob).order_by(desc(MonitorJob.created_at)).limit(10).all()
    return [
        {
            "job_id": j.id,
            "target_url": j.target_url,
            "status": j.status,
            "http_status_code": j.http_status_code,
            "response_time_ms": j.response_time_ms,
        }
        for j in jobs
    ]


@app.post("/jobs", status_code=202)
def create_monitor_job(payload: JobCreateRequest, db: Session = Depends(get_db)):
    job = MonitorJob(target_url=str(payload.target_url), status="PENDING")
    db.add(job)
    db.commit()
    db.refresh(job)

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
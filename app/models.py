import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from app.database import Base


class MonitorJob(Base):
    __tablename__ = "monitor_jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    target_url = Column(String, nullable=False, index=True)
    status = Column(String, default="PENDING", nullable=False)  # PENDING, COMPLETED, FAILED
    http_status_code = Column(Integer, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
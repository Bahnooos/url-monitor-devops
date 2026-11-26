FROM python:3.12-slim AS builder

WORKDIR /build

# to cache venv , prevent docker file for build venv in new layer every time i edit main.py    
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y pip setuptools wheel && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + && \
    find /opt/venv -type f -name "*.pyc" -delete

FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN apt-get update && \
    apt-get upgrade -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/* && \
    groupadd -r appgroup && useradd -r -g appgroup appuser

# 1. Layer المكتبات (بتتعملها Cache ومبتتغيرش غير لو requirements.txt اتعدلت)
COPY --from=builder /opt/venv /opt/venv

# 2. Layer كود التطبيق (خفيفة جداً وبتتحدث في ثواني مع كل تعديل)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
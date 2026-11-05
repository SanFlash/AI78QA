FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .
COPY apps/api/app ./app
COPY apps/worker/app ./worker
ENV PYTHONPATH=/app:/app/worker
CMD ["celery","-A","worker.tasks.celery_app","worker","--loglevel=INFO","--concurrency=2"]

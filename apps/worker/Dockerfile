FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./pyproject.toml
COPY apps/api/app ./app
# Merge worker entrypoints into the shared app package so API models/database resolve consistently.
COPY apps/worker/app/browser_discovery.py ./app/browser_discovery.py
COPY apps/worker/app/tasks.py ./app/worker_tasks.py
RUN pip install --no-cache-dir . playwright==1.51.0
ENV PYTHONPATH=/app
CMD ["celery","-A","app.worker_tasks.celery_app","worker","--loglevel=INFO","--concurrency=2"]

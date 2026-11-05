FROM mcr.microsoft.com/playwright/python:v1.51.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/pyproject.toml ./pyproject.toml
RUN pip install --no-cache-dir .
COPY apps/api/app ./app
# Merge worker modules into the shared app package so API models/database and browser worker resolve consistently.
COPY apps/worker/app/browser_discovery.py ./app/browser_discovery.py
COPY apps/worker/app/tasks.py ./app/worker_tasks.py
ENV PYTHONPATH=/app
CMD ["celery","-A","app.worker_tasks.celery_app","worker","--loglevel=INFO","--concurrency=2"]

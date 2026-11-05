# Deployment topology

- Vercel: Next.js web/control plane only (root directory: apps/web).
- Container host: FastAPI API and Celery worker.
- Managed PostgreSQL: persistent system of record.
- Managed Redis: job broker and worker coordination.
- Private S3-compatible storage: screenshots, traces, videos, model artifacts and reports.

For local development from repository root:
`docker compose -f infra/docker-compose.yml up --build`

For production, build apps/api/Dockerfile and apps/worker/Dockerfile from the repository root and provide DATABASE_URL and REDIS_URL to each. Deploy the web root as apps/web in Vercel and set NEXT_PUBLIC_API_BASE_URL to the public HTTPS API URL.

Vercel serverless request functions must not host long-lived browser sessions, Celery consumers or ML training workloads.

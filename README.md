# AI78QA — Autonomous QA Intelligence Platform

AI78QA is an AI-assisted QA engineering platform designed to discover websites, learn reusable UI patterns, produce traceable test cases, generate automation, execute tests, collect evidence, and improve from verified feedback.

## Product approach

- **Training Lab:** register authorized demo websites; explore pages; record DOM/accessibility observations and transitions; curate labelled datasets; evaluate model versions on unseen websites.
- **Production QA:** discover authorized applications; create manual test plans and test cases; generate editable Playwright/Selenium repositories; run web, API, accessibility, visual, performance and security checks within explicit policies; report defects and evidence.
- **Hybrid intelligence:** deterministic browser execution + provider-agnostic LLM reasoning + measurable classical ML models + application-specific knowledge. Website observations are not treated as ground truth until labelled or verified.
- **No silent self-healing:** locator repairs are proposed, validated, versioned and retested; original failures remain in history.

## Monorepo

- `apps/web`: Next.js control plane (deployable to Vercel).
- `apps/api`: FastAPI REST API and PostgreSQL domain layer (container deployment).
- `apps/worker`: Celery worker for discovery, Playwright/Selenium and report jobs (container deployment).
- `packages/contracts`: shared API/agent contracts.
- `ml/`: feature extraction, baseline models, evaluation and model cards.
- `infra/`: Docker Compose and deployment templates.
- `docs/`: architecture, safety, API and model evaluation plans.

## Free-first technology choices

Next.js, TypeScript, FastAPI, PostgreSQL, Redis, SQLAlchemy, Alembic, Celery, Playwright, Selenium, Pytest, scikit-learn, sentence-transformers (optional), MLflow (optional), Docker and GitHub Actions are open-source components. Hosted databases, object storage, LLM APIs and worker hosting may have free tiers or usage limits; no paid provider is required for the local baseline.

## Quick start

1. Copy `.env.example` to `.env` and set strong local credentials.
2. Start services: `docker compose -f infra/docker-compose.yml up --build`.
3. The API container applies Alembic migrations before serving requests.
4. Web: http://localhost:3000
5. API docs: http://localhost:8000/docs
6. In the web app Settings, set API base URL to `http://localhost:8000/api/v1`.

The control plane can be opened without an LLM key. Live registration and exploration require the API and worker to be deployed and the API base URL configured in the workspace. No model is promoted by default.

## Vercel deployment boundary

Vercel hosts the Next.js control plane. Browser automation and Celery workers run in separate containers. The browser talks to the same-origin `/api/ai78qa` proxy; the proxy injects `AI78QA_API_KEY` server-side and forwards to `AI78QA_API_URL`. Set `NEXT_PUBLIC_API_BASE_URL=/api/ai78qa` in the Vercel build environment. On the API service set `APP_ENV=production`, `API_ACCESS_KEY`, `DATABASE_URL`, and `REDIS_URL`. Set the same key as Vercel's server-only `AI78QA_API_KEY`. Never expose it through a `NEXT_PUBLIC_*` variable. Keep the Vercel project protected by SSO until proper user identity and tenant isolation are implemented.

## Security defaults

- Register only websites you own or are authorized to test.
- Explicit hostname allowlists; reject localhost, private, link-local and cloud metadata IP ranges by default.
- No arbitrary destructive actions, purchase/payment submission, messaging or uncontrolled load tests.
- Secrets are stored as secret references and never sent to prompts or written to logs.
- The current API is an internal single-workspace development API and does not yet implement user authentication or tenant isolation. Do not expose it publicly until API authentication, authorization, tenant isolation and rate limits are implemented.
- Tenant isolation, audit events, job timeouts, concurrency limits and evidence redaction are required before multi-user production use.

## Status

The current discovery worker performs bounded same-host crawling, inventories forms and UI elements, safely explores selected menu/tab/disclosure controls, records before/after UI state transitions, and exposes page/transition read APIs. See [Deep Browser Discovery](docs/DISCOVERY_ENGINE.md). The web build and Python checks are wired into GitHub Actions. This is a working discovery foundation—not yet a full autonomous QA suite: authenticated browser sessions, object-storage archival for large-scale evidence and browser traces, user-approved business transactions, cross-browser runs, full API testing, and production-grade identity/tenant isolation remain subsequent milestones. ML model performance must be measured on held-out websites before a model is described as transfer-ready.

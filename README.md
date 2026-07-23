# ModelOps Hub

Internal MLOps dashboard for model lifecycle governance, experiment tracking, deployment orchestration, and inference observability.

## Stack

- Backend: FastAPI + SQLAlchemy
- Frontend: React + TypeScript + Vite
- Data: PostgreSQL
- Cache: Redis (dashboard summary cache)
- Container: Docker / Docker Compose
- Deployment target: Railway (separate backend and frontend services)

## Core capabilities

- Model registry with version history
- Experiment tracking for parameters, metrics, artifacts
- Deployment workflow with canary and blue/green strategy states
- Inference log capture and latency/error metrics (avg and p95)
- Role-based access control (`admin` and `viewer`)

## Project structure

- `backend/`: FastAPI service
- `frontend/`: React dashboard
- `docker-compose.yml`: local full-stack runtime

## Local run (Docker)

1. Build and start all services:

   ```bash
   docker compose up --build
   ```

2. Open:
- Frontend: http://localhost:5173
- Backend API docs: http://localhost:8000/docs

Demo users are seeded automatically when the backend starts:
- Admin: `admin@modelops.local` / `admin1234`
- Viewer: `viewer@modelops.local` / `viewer1234`

## Local run (without Docker)

### Backend

1. Create an env file:

   ```bash
   cp backend/.env.example backend/.env
   ```

2. Install and run:

   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

### Frontend

1. Create an env file:

   ```bash
   cp frontend/.env.example frontend/.env
   ```

2. Install and run:

   ```bash
   cd frontend
   npm install
  npm run dev
   ```

Note for this Windows environment: if native binary npm packages hit `EPERM` locally, prefer running the app with Docker (`docker compose up --build`) or deploying to Railway (Linux build environment).

If local frontend install fails because `node_modules` cannot be removed on Windows:

```powershell
Set-Location frontend
attrib -r "node_modules\*" /s /d
cmd /c rmdir /s /q node_modules
Remove-Item -Force package-lock.json -ErrorAction SilentlyContinue
npm cache clean --force
npm install --legacy-peer-deps
```

## API overview

All routes are under `/api/v1`.

- Auth:
  - `POST /auth/login`
  - `POST /auth/register` (admin only)
- Model registry:
  - `GET /models`
  - `POST /models` (admin only)
  - `POST /models/{model_id}/versions` (admin only)
- Experiments:
  - `GET /experiments`
  - `POST /experiments` (admin only)
- Deployments:
  - `GET /deployments`
  - `POST /deployments` (admin only)
  - `PATCH /deployments/{deployment_id}/status` (admin only)
- Inference:
  - `GET /inference/logs`
  - `POST /inference/logs`
  - `GET /inference/metrics`
- Dashboard:
  - `GET /dashboard/summary`

## Migrations

Alembic is configured under `backend/alembic` with the initial schema revision in `backend/alembic/versions/20260715_0001_initial.py`.

Run migrations:

```bash
cd backend
alembic upgrade head
```

Create a new migration after model changes:

```bash
cd backend
alembic revision --autogenerate -m "describe change"
```

## Testing

Backend API tests cover:

- Auth + RBAC (`admin` vs `viewer`)
- Model/version/deployment lifecycle flow
- Inference metrics calculations
- Dashboard summary counts + Redis cache behavior
- Cache invalidation on model/version, experiment, deployment, and inference writes

Dashboard summary cache is automatically invalidated on lifecycle writes (model/version registration, experiment tracking, deployment changes, and inference log ingestion) so observability and governance counters stay fresh.

Run tests:

```bash
cd backend
pytest -q
```

These tests expect PostgreSQL and Redis reachable via `DATABASE_URL` and `REDIS_URL`.

## CI

GitHub Actions workflow at `.github/workflows/ci.yml` runs:

- Backend: dependency install, `alembic upgrade head`, `pytest -q`
- Frontend: dependency install and `npm run build`

## One-command verification

Run the full verification flow (PostgreSQL + Redis startup, backend migration/tests, and frontend image build) with:

- Windows PowerShell:

```powershell
./scripts/verify.ps1
```

- Linux/macOS:

```bash
./scripts/verify.sh
```

Both scripts are fail-fast: if migrations/tests/build fail, the script exits with a non-zero status.
For deterministic test runs, verification resets the `modelops` database schema before applying migrations.

Fast repeat checks (skip frontend image build):

- Windows PowerShell:

```powershell
./scripts/verify.ps1 -Fast
```

- Linux/macOS:

```bash
FAST_MODE=1 ./scripts/verify.sh
```

## Railway deployment

Railway supports this architecture with separate services and managed data stores.

1. Push this repository to GitHub.
2. Create a Railway project.
3. Add two services from the same repo:
- Backend service:
  - Root directory: `backend`
  - Use Dockerfile in `backend/Dockerfile`
  - Environment variables:
    - `DATABASE_URL` (from Railway Postgres)
    - `REDIS_URL` (from Railway Redis)
    - `JWT_SECRET` (strong random value)
    - `CORS_ORIGINS` (your frontend Railway URL)
- Frontend service:
  - Root directory: `frontend`
  - Use Dockerfile in `frontend/Dockerfile`

4. Add Railway PostgreSQL and Railway Redis plugins.
5. Attach `DATABASE_URL` and `REDIS_URL` references to backend service.
6. Redeploy both services.

## Governance and platform fit

This project emphasizes platform-level concerns aligned to internal AI platform teams:

- Governance: structured model/version lifecycle and RBAC boundaries
- Observability: latency/error metrics and inference event logs
- Controlled rollout: canary/blue-green status workflows
- API-first extensibility: REST endpoints ready for CI/CD or orchestration hooks

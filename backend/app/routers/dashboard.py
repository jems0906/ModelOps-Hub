import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cache import DASHBOARD_SUMMARY_KEY, async_redis_client
from app.db import get_db
from app.deps import get_current_user
from app.models import Deployment, DeployStatus, Experiment, InferenceLog, ModelRegistry, ModelVersion, User
from app.schemas import DashboardSummaryOut, InferenceMetricsOut

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryOut)
async def summary(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    cached = await async_redis_client.get(DASHBOARD_SUMMARY_KEY)
    if cached:
        data = json.loads(cached)
        data["inference_metrics"] = InferenceMetricsOut(**data["inference_metrics"])
        return DashboardSummaryOut(**data)

    logs = db.query(InferenceLog).all()
    total_requests = len(logs)
    avg_latency = round(sum(item.latency_ms for item in logs) / total_requests, 2) if total_requests else 0.0
    errors = len([item for item in logs if item.status_code >= 400])

    if total_requests:
        latencies = sorted(item.latency_ms for item in logs)
        p95_idx = max(int(0.95 * total_requests) - 1, 0)
        p95_latency = round(latencies[p95_idx], 2)
    else:
        p95_latency = 0.0

    payload = DashboardSummaryOut(
        total_models=db.query(ModelRegistry).count(),
        total_versions=db.query(ModelVersion).count(),
        total_experiments=db.query(Experiment).count(),
        active_deployments=db.query(Deployment).filter(Deployment.status == DeployStatus.running).count(),
        inference_metrics=InferenceMetricsOut(
            total_requests=total_requests,
            error_rate=round(errors / total_requests, 4) if total_requests else 0.0,
            avg_latency_ms=avg_latency,
            p95_latency_ms=p95_latency,
        ),
    )

    await async_redis_client.set(DASHBOARD_SUMMARY_KEY, payload.model_dump_json(), ex=30)
    return payload

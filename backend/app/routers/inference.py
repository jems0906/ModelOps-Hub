from statistics import mean

from fastapi import APIRouter, Depends

from app.core.cache import invalidate_dashboard_summary_cache
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import InferenceLog, User
from app.schemas import InferenceLogCreate, InferenceLogOut, InferenceMetricsOut

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("/logs", response_model=InferenceLogOut)
def create_log(payload: InferenceLogCreate, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    log = InferenceLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    invalidate_dashboard_summary_cache()
    return log


@router.get("/logs", response_model=list[InferenceLogOut])
def list_logs(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(InferenceLog).order_by(InferenceLog.created_at.desc()).limit(200).all()


@router.get("/metrics", response_model=InferenceMetricsOut)
def metrics(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    logs = db.query(InferenceLog).all()
    if not logs:
        return InferenceMetricsOut(total_requests=0, error_rate=0.0, avg_latency_ms=0.0, p95_latency_ms=0.0)

    latencies = sorted([item.latency_ms for item in logs])
    errors = [item for item in logs if item.status_code >= 400]

    idx = max(int(0.95 * len(latencies)) - 1, 0)
    p95 = latencies[idx]

    return InferenceMetricsOut(
        total_requests=len(logs),
        error_rate=round(len(errors) / len(logs), 4),
        avg_latency_ms=round(mean(latencies), 2),
        p95_latency_ms=round(p95, 2),
    )

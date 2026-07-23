from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import invalidate_dashboard_summary_cache
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import Deployment, ModelVersion, User
from app.schemas import DeploymentCreate, DeploymentOut, DeploymentStatusUpdate

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.get("", response_model=list[DeploymentOut])
def list_deployments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Deployment).order_by(Deployment.created_at.desc()).all()


@router.post("", response_model=DeploymentOut)
def create_deployment(payload: DeploymentCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    version = db.query(ModelVersion).filter(ModelVersion.id == payload.model_version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found")

    deployment = Deployment(**payload.model_dump())
    db.add(deployment)
    db.commit()
    db.refresh(deployment)
    invalidate_dashboard_summary_cache()
    return deployment


@router.patch("/{deployment_id}/status", response_model=DeploymentOut)
def update_status(deployment_id: int, payload: DeploymentStatusUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deployment not found")

    deployment.status = payload.status
    deployment.traffic_percent = payload.traffic_percent
    db.commit()
    db.refresh(deployment)
    invalidate_dashboard_summary_cache()
    return deployment

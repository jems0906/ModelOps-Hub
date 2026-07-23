from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import invalidate_dashboard_summary_cache
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import Experiment, ModelVersion, User
from app.schemas import ExperimentCreate, ExperimentOut

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("", response_model=list[ExperimentOut])
def list_experiments(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Experiment).order_by(Experiment.created_at.desc()).all()


@router.post("", response_model=ExperimentOut)
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    version = db.query(ModelVersion).filter(ModelVersion.id == payload.model_version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model version not found")

    experiment = Experiment(**payload.model_dump())
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    invalidate_dashboard_summary_cache()
    return experiment

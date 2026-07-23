from fastapi import APIRouter, Depends, HTTPException, status

from app.core.cache import invalidate_dashboard_summary_cache
from sqlalchemy.orm import Session, joinedload

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import ModelRegistry, ModelVersion, User
from app.schemas import ModelCreate, ModelOut, ModelVersionCreate, ModelVersionOut

router = APIRouter(prefix="/models", tags=["model-registry"])


@router.get("", response_model=list[ModelOut])
def list_models(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ModelRegistry).options(joinedload(ModelRegistry.versions)).order_by(ModelRegistry.created_at.desc()).all()


@router.post("", response_model=ModelOut)
def create_model(payload: ModelCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    existing = db.query(ModelRegistry).filter(ModelRegistry.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Model already exists")

    model = ModelRegistry(**payload.model_dump())
    db.add(model)
    db.commit()
    db.refresh(model)
    invalidate_dashboard_summary_cache()
    return model


@router.post("/{model_id}/versions", response_model=ModelVersionOut)
def add_model_version(model_id: int, payload: ModelVersionCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    model = db.query(ModelRegistry).filter(ModelRegistry.id == model_id).first()
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")

    version = ModelVersion(model_id=model_id, created_by=user.email, **payload.model_dump())
    db.add(version)
    db.commit()
    db.refresh(version)
    invalidate_dashboard_summary_cache()
    return version

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import DeployStatus, DeployStrategy, UserRole


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole


class UserCreate(UserBase):
    password: str = Field(min_length=8)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class ModelCreate(BaseModel):
    name: str
    description: str = ""
    owner_team: str


class ModelVersionCreate(BaseModel):
    version_tag: str
    artifact_uri: str
    changelog: str = ""


class ModelVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_id: int
    version_tag: str
    artifact_uri: str
    changelog: str
    created_by: str
    created_at: datetime


class ModelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    owner_team: str
    created_at: datetime
    versions: list[ModelVersionOut] = []


class ExperimentCreate(BaseModel):
    model_version_id: int
    run_name: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    artifact_uri: str
    status: str = "completed"


class ExperimentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_version_id: int
    run_name: str
    parameters: dict[str, Any]
    metrics: dict[str, Any]
    artifact_uri: str
    status: str
    created_at: datetime


class DeploymentCreate(BaseModel):
    model_version_id: int
    environment: str = "staging"
    strategy: DeployStrategy
    status: DeployStatus = DeployStatus.pending
    traffic_percent: int = Field(ge=0, le=100, default=0)
    notes: str = ""


class DeploymentStatusUpdate(BaseModel):
    status: DeployStatus
    traffic_percent: int = Field(ge=0, le=100, default=0)


class DeploymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_version_id: int
    environment: str
    strategy: DeployStrategy
    status: DeployStatus
    traffic_percent: int
    notes: str
    created_at: datetime


class InferenceLogCreate(BaseModel):
    model_version_id: int
    request_id: str
    latency_ms: float = Field(ge=0)
    status_code: int
    error_message: str = ""


class InferenceLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model_version_id: int
    request_id: str
    latency_ms: float
    status_code: int
    error_message: str
    created_at: datetime


class InferenceMetricsOut(BaseModel):
    total_requests: int
    error_rate: float
    avg_latency_ms: float
    p95_latency_ms: float


class DashboardSummaryOut(BaseModel):
    total_models: int
    total_versions: int
    total_experiments: int
    active_deployments: int
    inference_metrics: InferenceMetricsOut

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ModelVersionsResponse(BaseModel):
    class ModelVersion(BaseModel):
        model_id: str
        model_name: str
        version: str
        status: str
        created_at: datetime

    models: List[ModelVersion]


class ModelDeployRequest(BaseModel):
    model_id: str
    version: str


class ModelDeployResponse(BaseModel):
    deployment_id: str
    status: str
    deployment_time: datetime


class ModelPerformanceResponse(BaseModel):
    model_id: str
    accuracy: float
    precision: float
    recall: float
    latency_ms: int

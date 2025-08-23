# app/features/management/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from .schemas import *
from . import service

router = APIRouter()


@router.get(
    "/models/versions", response_model=ModelVersionsResponse, tags=["Model Management"]
)
def list_model_versions(db: Session = Depends(get_db)):
    return service.get_model_versions(db)


@router.post(
    "/models/deploy", response_model=ModelDeployResponse, tags=["Model Management"]
)
def deploy_model_version(request: ModelDeployRequest, db: Session = Depends(get_db)):
    return service.deploy_model(db, request)


@router.get(
    "/models/performance",
    response_model=ModelPerformanceResponse,
    tags=["Model Management"],
)
def get_model_performance_metrics(model_id: str, db: Session = Depends(get_db)):
    return service.get_model_performance(db, model_id)

from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.get(
    "/models/versions", response_model=ModelVersionsResponse, tags=["Model Management"]
)
def list_model_versions():
    """
    Retrieves a list of available ML model versions and their status.
    """
    return service.get_model_versions()


@router.post(
    "/models/deploy", response_model=ModelDeployResponse, tags=["Model Management"]
)
def deploy_model_version(request: ModelDeployRequest):
    """Deploys a specific model version to production."""
    return service.deploy_model(request)


@router.get(
    "/models/performance",
    response_model=ModelPerformanceResponse,
    tags=["Model Management"],
)
def get_model_performance_metrics(model_id: str):
    """Retrieves performance metrics for a specific deployed model."""
    return service.get_model_performance(model_id)

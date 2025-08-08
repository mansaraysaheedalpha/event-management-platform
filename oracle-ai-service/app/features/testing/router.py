from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/ab-testing/experiments",
    response_model=ABTestExperimentResponse,
    tags=["A/B Testing"],
)
def create_ab_test_experiment(request: ABTestExperimentRequest):
    """
    Creates a new A/B testing experiment to compare model versions.
    """
    return service.create_ab_test(request)


@router.get(
    "/ab-testing/results", response_model=ABTestResultsResponse, tags=["A/B Testing"]
)
def get_ab_test_results(experiment_id: str):
    """Retrieves the results from a specific A/B testing experiment."""
    return service.get_ab_test_results(experiment_id)

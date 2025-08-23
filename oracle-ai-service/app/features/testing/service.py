# app/features/testing/service.py
import uuid
from datetime import datetime, timedelta, timezone
from .schemas import *


def _save_experiment_to_db(request: ABTestExperimentRequest) -> str:
    """Simulates saving a new A/B test experiment to a database."""
    experiment_id = f"exp_{uuid.uuid4().hex[:12]}"
    print(f"Simulating DB write for new A/B test: {experiment_id}")
    return experiment_id


def _get_results_from_db(experiment_id: str) -> dict:
    """Simulates querying a data warehouse for A/B test results."""
    print(f"Simulating DB query for results of A/B test: {experiment_id}")
    return {
        "status": "completed",
        "results": [
            {
                "variant_name": "Control (Model A)",
                "is_winner": False,
                "performance": {"engagement_score": 85.2},
            },
            {
                "variant_name": "Challenger (Model B)",
                "is_winner": True,
                "performance": {"engagement_score": 88.9},
            },
        ],
        "conclusion": "Challenger (Model B) showed a statistically significant improvement.",
    }


def create_ab_test(request: ABTestExperimentRequest) -> ABTestExperimentResponse:
    """Creates and registers a new A/B testing experiment."""
    # In a real system, you'd have more validation here, e.g.,
    # ensuring traffic allocations sum to 1.0.

    experiment_id = _save_experiment_to_db(request)
    start_time = datetime.now(timezone.utc)

    return ABTestExperimentResponse(
        experiment_id=experiment_id,
        status="created",
        start_time=start_time,
        estimated_end_time=start_time + timedelta(days=14),
    )


def get_ab_test_results(experiment_id: str) -> ABTestResultsResponse:
    """Retrieves the results for a completed A/B test experiment."""
    results_data = _get_results_from_db(experiment_id)

    return ABTestResultsResponse(experiment_id=experiment_id, **results_data)

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
        "experiment_name": "Model Comparison Test",
        "status": "completed",
        "results": [
            {
                "variant_name": "Control (Model A)",
                "is_winner": False,
                "metrics": {
                    "engagement_score": 85.2,
                    "conversion_rate": 3.4,
                    "avg_session_duration": 245.0,
                },
                "improvement_percentage": 0.0,  # Baseline
            },
            {
                "variant_name": "Challenger (Model B)",
                "is_winner": True,
                "metrics": {
                    "engagement_score": 88.9,
                    "conversion_rate": 4.1,
                    "avg_session_duration": 267.0,
                },
                "improvement_percentage": 4.3,
            },
        ],
        "conclusion": "Challenger (Model B) showed a statistically significant improvement of 4.3% in overall performance.",
    }


def create_ab_test(request: ABTestExperimentRequest) -> ABTestExperimentResponse:
    """Creates and registers a new A/B testing experiment with optimized response structure."""
    # Validate traffic allocations sum to 1.0 (or close to it)
    total_traffic = sum(variant.traffic for variant in request.model_variants)
    if not (0.99 <= total_traffic <= 1.01):
        # In a real system, would raise HTTPException
        print(f"Warning: Traffic allocations sum to {total_traffic}, expected 1.0")
    
    experiment_id = _save_experiment_to_db(request)
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(days=14)
    
    # Convert variants to compact format for response
    variants = [
        {
            "name": v.name,
            "model": f"{v.model_id}@{v.version}",
            "traffic_pct": v.traffic_percentage,
            "description": v.description or "",
        }
        for v in request.model_variants
    ]
    
    # Create response with computed summary
    return ABTestExperimentResponse.create_with_summary(
        experiment_id=experiment_id,
        name=request.experiment_name,
        status="created",
        start_time=start_time,
        estimated_end_time=end_time,
        variants=variants,
    )


def get_ab_test_results(experiment_id: str) -> ABTestResultsResponse:
    """Retrieves the results for a completed A/B test experiment with enhanced metrics."""
    results_data = _get_results_from_db(experiment_id)
    
    # Convert raw results to optimized VariantResult objects
    variant_results = [
        ABTestResultsResponse.VariantResult.create_with_highlights(
            variant_name=r["variant_name"],
            is_winner=r["is_winner"],
            metrics=r["metrics"],
            improvement=r.get("improvement_percentage")
        )
        for r in results_data["results"]
    ]
    
    # Create response with computed statistics and recommendation
    return ABTestResultsResponse.create_with_stats(
        experiment_id=experiment_id,
        experiment_name=results_data["experiment_name"],
        status=results_data["status"],
        results=variant_results,
        conclusion=results_data["conclusion"],
    )

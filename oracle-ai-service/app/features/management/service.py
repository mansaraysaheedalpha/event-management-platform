from datetime import datetime, timezone
import uuid
import random
from app.features.management.schemas import (
    ModelVersionsResponse,
    ModelDeployRequest,
    ModelDeployResponse,
    ModelPerformanceResponse,
)


def get_model_versions() -> ModelVersionsResponse:
    """
    This service function retrieves the versions of available ML models.
    In a real system, this might query a model registry like MLflow or a database table.

    For now, we return a hardcoded, realistic list of models.
    """
    models = [
        ModelVersionsResponse.ModelVersion(
            model_id="sentiment_analysis_v2",
            model_name="DistilBERT-SST2",
            version="2.1.3",
            status="active",
            created_at=datetime(2025, 7, 15, 10, 0, 0, tzinfo=timezone.utc),
        ),
        ModelVersionsResponse.ModelVersion(
            model_id="churn_prediction_xgb",
            model_name="XGBoost Churn Classifier",
            version="1.4.0",
            status="active",
            created_at=datetime(2025, 6, 20, 14, 30, 0, tzinfo=timezone.utc),
        ),
    ]

    return ModelVersionsResponse(models=models)


def deploy_model(request: ModelDeployRequest) -> ModelDeployResponse:
    """Simulates deploying a specific model version."""
    return ModelDeployResponse(
        deployment_id=f"deploy_{uuid.uuid4().hex[:12]}",
        status="in_progress",
        deployment_time=datetime.now(timezone.utc),
    )


def get_model_performance(model_id: str) -> ModelPerformanceResponse:
    """Simulates retrieving performance metrics for a deployed model."""
    return ModelPerformanceResponse(
        model_id=model_id,
        accuracy=round(random.uniform(0.85, 0.98), 2),
        precision=round(random.uniform(0.88, 0.99), 2),
        recall=round(random.uniform(0.82, 0.96), 2),
        latency_ms=random.randint(50, 150),
    )

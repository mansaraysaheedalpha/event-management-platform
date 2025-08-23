# tests/features/test_management_service.py
import pytest
from fastapi import HTTPException
from app.features.management.service import *
from app.features.management.schemas import *


def test_get_model_versions_retrieves_from_db(mocker):
    mock_registry_data = [
        {
            "sentiment_analysis_v2": {
                "model_id": "sentiment_analysis_v2",
                "model_name": "DistilBERT-SST2",
                "version": "2.1.3",
                "status": "active",
                "created_at": "2025-07-15T10:00:00Z",
            }
        }
    ]
    mocker.patch(
        "app.features.management.service.crud.get_kb_category",
        return_value=mock_registry_data,
    )
    response = get_model_versions(db=None)  # db=None because it's mocked
    assert len(response.models) == 1
    assert response.models[0].model_name == "DistilBERT-SST2"


def test_deploy_model_succeeds_for_existing_model(mocker):
    request = ModelDeployRequest(model_id="sentiment_analysis_v2", version="2.1.3")
    mock_model_data = {"version": "2.1.3"}
    mock_trigger = mocker.patch(
        "app.features.management.service.deployment_client.trigger"
    )
    response = deploy_model(db=None, request=request)
    assert response.status == "in_progress"
    mock_trigger.assert_called_once_with(
        model_id="sentiment_analysis_v2", version=mock_model_data
    )


def test_deploy_model_fails_for_non_existent_model(mocker):
    request = ModelDeployRequest(model_id="non_existent_model", version="1.0.0")
    mock_trigger = mocker.patch(
        "app.features.management.service.deployment_client.trigger"
    )  # Mock DB returning nothing
    with pytest.raises(HTTPException) as exc_info:
        deploy_model(db=None, request=request)
    assert exc_info.value.status_code == 404
    mock_trigger.assert_not_called()


def test_get_model_performance_succeeds_for_existing_model(mocker):
    model_id = "churn_prediction_xgb"
    mock_metrics = {"accuracy": 0.92, "precision": 0.88, "recall": 0.90, "latency_ms": 120}
    mocker.patch(
        "app.features.management.service.monitoring_client.get_metrics",
        return_value=mock_metrics,
    )
    response = get_model_performance(db=None, model_id=model_id)
    assert response.model_id == model_id
    assert response.accuracy > 0


def test_get_model_performance_fails_for_non_existent_model(mocker):
    model_id = "non_existent_model"
    mocker.patch(
        "app.features.management.service.crud.get_kb_entry", return_value={}
    )  # Mock DB confirms model does NOT exist
    with pytest.raises(HTTPException) as exc_info:
        get_model_performance(db=None, model_id=model_id)
    assert exc_info.value.status_code == 404

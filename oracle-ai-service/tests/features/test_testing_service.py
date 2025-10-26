# tests/features/test_testing_service.py

import pytest
from app.features.testing.service import create_ab_test, get_ab_test_results
from app.features.testing.schemas import ABTestExperimentRequest


def test_create_ab_test_experiment(mocker):
    """
    Tests that a new A/B test experiment can be successfully created with improved compact response structure.
    """
    # 1. Arrange
    request = ABTestExperimentRequest(
        experiment_name="Test Engagement Models",
        description="Testing new model variants",
        model_variants=[
            ABTestExperimentRequest.ModelVariant(
                name="Control",
                model_id="engagement_v1",
                version="1.0",
                traffic=0.5,  # Updated field name
                description="Current model"
            ),
            ABTestExperimentRequest.ModelVariant(
                name="Challenger",
                model_id="engagement_v2",
                version="1.1",
                traffic=0.5,  # Updated field name
                description="New model"
            ),
        ],
    )
    mock_save = mocker.patch(
        "app.features.testing.service._save_experiment_to_db", return_value="exp_12345"
    )

    # 2. Act
    response = create_ab_test(request)

    # 3. Assert
    mock_save.assert_called_once_with(request)
    assert response.experiment_id == "exp_12345"
    assert response.name == "Test Engagement Models"
    assert response.status == "created"
    
    # Verify new compact response fields
    assert hasattr(response, 'summary'), "Response should have summary field"
    assert hasattr(response, 'variants'), "Response should have variants field"
    assert response.summary["variant_count"] == 2, "Summary should show 2 variants"
    assert len(response.variants) == 2, "Should have 2 variants in response"
    
    # Verify compact variant structure
    assert "name" in response.variants[0], "Variant should have name"
    assert "model" in response.variants[0], "Variant should have model"
    assert "traffic_pct" in response.variants[0], "Variant should have traffic_pct"


def test_get_ab_test_results(mocker):
    """
    Tests that the results for a given experiment ID are retrieved correctly with metric highlights.
    """
    # 1. Arrange
    experiment_id = "exp_abcde"
    mock_results = {
        "experiment_name": "Test Experiment",
        "status": "completed",
        "results": [
            {
                "variant_name": "Control",
                "is_winner": False,
                "metrics": {"engagement_score": 85.2},
                "improvement_percentage": 0.0
            }
        ],
        "conclusion": "Control was not the winner.",
    }
    mocker.patch(
        "app.features.testing.service._get_results_from_db", return_value=mock_results
    )

    # 2. Act
    response = get_ab_test_results(experiment_id)

    # 3. Assert
    assert response.experiment_id == experiment_id
    assert response.experiment_name == "Test Experiment"
    assert response.status == "completed"
    assert response.conclusion == "Control was not the winner."
    assert len(response.results) == 1
    
    # Verify new compact result fields
    assert hasattr(response, 'summary_stats'), "Response should have summary_stats"
    assert hasattr(response, 'recommendation'), "Response should have recommendation"
    
    # Verify variant result improvements
    result = response.results[0]
    assert hasattr(result, 'metric_highlights'), "Result should have metric_highlights"
    assert hasattr(result, 'improvement_percentage'), "Result should have improvement_percentage"
    assert result.improvement_percentage == 0.0, "Control should have 0% improvement"

# tests/features/test_testing_service.py

import pytest
from app.features.testing.service import create_ab_test, get_ab_test_results
from app.features.testing.schemas import ABTestExperimentRequest


def test_create_ab_test_experiment(mocker):
    """
    Tests that a new A/B test experiment can be successfully created.
    """
    # 1. Arrange
    request = ABTestExperimentRequest(
        experiment_name="Test Engagement Models",
        model_variants=[
            ABTestExperimentRequest.ModelVariant(
                variant_name="Control",
                model_id="engagement_v1",
                model_version="1.0",
                traffic_allocation=0.5,
            ),
            ABTestExperimentRequest.ModelVariant(
                variant_name="Challenger",
                model_id="engagement_v2",
                model_version="1.1",
                traffic_allocation=0.5,
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
    assert response.status == "created"


def test_get_ab_test_results(mocker):
    """
    Tests that the results for a given experiment ID are retrieved correctly.
    """
    # 1. Arrange
    experiment_id = "exp_abcde"
    mock_results = {
        "status": "completed",
        "results": [{"variant_name": "Control", "is_winner": False, "performance": {}}],
        "conclusion": "Control was not the winner.",
    }
    mocker.patch(
        "app.features.testing.service._get_results_from_db", return_value=mock_results
    )

    # 2. Act
    response = get_ab_test_results(experiment_id)

    # 3. Assert
    assert response.experiment_id == experiment_id
    assert response.status == "completed"
    assert response.conclusion == "Control was not the winner."
    assert len(response.results) == 1

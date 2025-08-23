# tests/features/test_reporting_service.py

import pytest
from app.features.reporting.service import *
from app.features.reporting.schemas import *


def test_generate_insights_finds_correlation(mocker):
    """
    Tests that the insight engine can identify a correlation between
    high session engagement and positive overall sentiment.
    """
    # 1. Arrange
    request = InsightsRequest(
        event_id="evt_123", data_sources=["engagement", "sentiment"]
    )

    # Mock the helper functions that would fetch data from other services or databases
    mocker.patch(
        "app.features.reporting.service._get_overall_sentiment", return_value=0.8
    )
    mocker.patch(
        "app.features.reporting.service._get_top_session", return_value="Advanced AI"
    )

    # 2. Act
    response = generate_insights(request)

    # 3. Assert
    assert len(response.insights) >= 1

    # Find the specific insight we expect the engine to generate
    correlation_insight = next(
        (i for i in response.insights if i.category == "correlation"), None
    )

    assert correlation_insight is not None
    assert "positive sentiment" in correlation_insight.title.lower()
    assert "Advanced AI" in correlation_insight.description


def test_benchmark_event_interprets_performance_correctly(mocker):
    """
    Tests that the benchmarking service correctly compares event metrics against
    a benchmark and provides the right interpretation.
    """
    # 1. Arrange
    request = BenchmarkingRequest(
        event_id="evt_123", comparison_group="industry_average"
    )

    # Mock the two data sources our service will need
    mocker.patch(
        "app.features.reporting.service._get_current_event_metrics",
        return_value={"engagement_score": 85.0, "roi": 0.9},
    )
    mocker.patch(
        "app.features.reporting.service._get_benchmark_metrics",
        return_value={"engagement_score": 75.0, "roi": 1.2},
    )

    # 2. Act
    response = benchmark_event(request)

    # 3. Assert
    assert len(response.benchmarks) == 2
    benchmarks = {b.metric: b for b in response.benchmarks}

    # Check engagement score: 85 is well above the benchmark of 75 -> top_performer
    assert benchmarks["engagement_score"].event_value == 85.0
    assert benchmarks["engagement_score"].benchmark_value == 75.0
    assert benchmarks["engagement_score"].interpretation == "top_performer"

    # Check ROI: 0.9 is below the benchmark of 1.2 -> below_average
    assert benchmarks["roi"].event_value == 0.9
    assert benchmarks["roi"].benchmark_value == 1.2
    assert benchmarks["roi"].interpretation == "below_average"

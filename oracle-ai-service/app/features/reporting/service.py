# app/features/reporting/service.py

import uuid
from datetime import datetime, timezone
from .schemas import *


# --- Mock Data Fetchers ---
# In a real system, these would be complex queries.
def _get_overall_sentiment(event_id: str) -> float:
    print(f"Simulating fetch for sentiment data for event {event_id}")
    return 0.8  # Highly positive


def _get_top_session(event_id: str) -> str:
    print(f"Simulating fetch for engagement data for event {event_id}")
    return "Advanced AI"


# --- Main Service Function ---
def generate_insights(request: InsightsRequest) -> InsightsResponse:
    """
    Generates key insights by applying a set of rules to aggregated event data.
    """
    # 1. "Fetch" our aggregated data
    sentiment_score = _get_overall_sentiment(request.event_id)
    top_session_topic = _get_top_session(request.event_id)

    insights = []

    # --- Composite Heuristic Rules Engine ---

    # Rule 1: Look for a correlation between high sentiment and an engaging session.
    if sentiment_score > 0.6 and top_session_topic == "Advanced AI":
        insights.append(
            InsightsResponse.Insight(
                insight_id=f"ins_{uuid.uuid4().hex[:8]}",
                title="Positive Sentiment Driven by High Engagement in AI Sessions",
                description=f"The overall positive event sentiment appears to be strongly correlated with the high engagement observed in the '{top_session_topic}' session.",
                category="correlation",
                severity="high",
                supporting_data={
                    "sentiment_score": sentiment_score,
                    "top_session": top_session_topic,
                },
            )
        )

    # (More rules would be added here to find other types of insights)

    return InsightsResponse(
        event_id=request.event_id,
        generated_at=datetime.now(timezone.utc),
        insights=insights,
    )


# --- Mock Data Fetchers for Benchmarking ---
def _get_current_event_metrics(event_id: str) -> dict:
    """Simulates fetching key metrics for a specific event."""
    print(f"Fetching metrics for event {event_id}")
    return {"engagement_score": 85.0, "roi": 0.9, "attendee_satisfaction": 0.92}


def _get_benchmark_metrics(comparison_group: str) -> dict:
    """Simulates fetching aggregated metrics for a comparison group."""
    print(f"Fetching benchmark metrics for {comparison_group}")
    if comparison_group == "industry_average":
        return {"engagement_score": 75.0, "roi": 1.2, "attendee_satisfaction": 0.88}
    return {}


# --- New Service Function ---
def benchmark_event(request: BenchmarkingRequest) -> BenchmarkingResponse:
    """
    Compares an event's key metrics against a selected benchmark group.
    """
    event_metrics = _get_current_event_metrics(request.event_id)
    benchmark_metrics = _get_benchmark_metrics(request.comparison_group)

    benchmarks = []
    for metric, event_value in event_metrics.items():
        if metric in benchmark_metrics:
            benchmark_value = benchmark_metrics[metric]

            # --- Comparison Logic Engine ---
            interpretation = "average"
            # If event value is >10% better than benchmark -> top_performer
            if event_value > benchmark_value * 1.1:
                interpretation = "top_performer"
            # If event value is >10% worse than benchmark -> below_average
            elif event_value < benchmark_value * 0.9:
                interpretation = "below_average"

            benchmarks.append(
                BenchmarkingResponse.Benchmark(
                    metric=metric,
                    event_value=event_value,
                    benchmark_value=benchmark_value,
                    interpretation=interpretation,
                )
            )

    return BenchmarkingResponse(benchmarks=benchmarks)

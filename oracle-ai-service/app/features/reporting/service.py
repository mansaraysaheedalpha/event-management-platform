import uuid
from datetime import datetime, timezone
from app.features.reporting.schemas import (
    InsightsRequest,
    InsightsResponse,
    BenchmarkingRequest,
    BenchmarkingResponse,
)


def generate_insights(request: InsightsRequest) -> InsightsResponse:
    """
    This service function simulates an AI analyzing event data to generate insights.
    In a real system, this would trigger a complex data analysis pipeline,
    querying various data sources and applying statistical models.

    For now, we return a hardcoded, realistic set of insights.
    """
    insights = [
        InsightsResponse.Insight(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            title="High Engagement in 'Microservices' Session",
            description="The 'Advanced Microservice Architecture' session shows a 35% higher chat message volume compared to other technical sessions, indicating strong attendee interest.",
            category="trend",
            severity="medium",
            supporting_data={"session_id": "ses_1234", "chat_volume_increase": 0.35},
        ),
        InsightsResponse.Insight(
            insight_id=f"ins_{uuid.uuid4().hex[:8]}",
            title="Anomaly Detected: Low Networking Activity",
            description="The number of new network connections made in the last hour is 50% below the predicted average for this time of day.",
            category="anomaly",
            severity="high",
            supporting_data={"current_connection_rate": 15, "predicted_rate": 30},
        ),
    ]

    return InsightsResponse(
        event_id=request.event_id,
        generated_at=datetime.now(timezone.utc),
        insights=insights,
    )


def get_benchmarks(request: BenchmarkingRequest) -> BenchmarkingResponse:
    """Simulates comparing event performance against historical data."""
    benchmarks = [
        BenchmarkingResponse.Benchmark(
            metric="engagement_score",
            event_value=85.5,
            benchmark_value=75.0,
            interpretation="top_performer",
        ),
        BenchmarkingResponse.Benchmark(
            metric="roi",
            event_value=1.5,
            benchmark_value=1.8,
            interpretation="below_average",
        ),
    ]
    return BenchmarkingResponse(benchmarks=benchmarks)

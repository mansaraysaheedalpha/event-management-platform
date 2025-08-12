from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class InsightsRequest(BaseModel):
    event_id: str
    data_sources: List[str] = Field(
        ..., example=["attendance", "engagement", "sentiment"]
    )


class InsightsResponse(BaseModel):
    class Insight(BaseModel):
        insight_id: str
        title: str
        description: str
        category: str  # e.g., trend, anomaly, correlation
        severity: str  # e.g., low, medium, high
        supporting_data: Dict[str, Any]

    event_id: str
    generated_at: datetime
    insights: List[Insight]


class BenchmarkingRequest(BaseModel):
    event_id: str
    comparison_group: str = Field(..., example="industry_average")


class BenchmarkingResponse(BaseModel):
    class Benchmark(BaseModel):
        metric: str
        event_value: float
        benchmark_value: float
        interpretation: str

    benchmarks: List[Benchmark]

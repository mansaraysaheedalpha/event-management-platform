# app/features/testing/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ABTestExperimentRequest(BaseModel):
    class ModelVariant(BaseModel):
        variant_name: str
        model_id: str
        model_version: str
        traffic_allocation: float = Field(..., ge=0, le=1)

    experiment_name: str
    model_variants: List[ModelVariant]


class ABTestExperimentResponse(BaseModel):
    experiment_id: str
    status: str
    start_time: datetime
    estimated_end_time: datetime
    dashboard_url: str = "https://your-analytics-platform.com/ab-test/dashboard"


class ABTestResultsResponse(BaseModel):
    class VariantResult(BaseModel):
        variant_name: str
        is_winner: bool
        performance: dict

    experiment_id: str
    status: str
    results: List[VariantResult]
    conclusion: str

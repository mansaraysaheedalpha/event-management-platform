from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/reporting/insights",
    response_model=InsightsResponse,
    tags=["Advanced Analytics & Reporting"],
)
def get_generated_insights(request: InsightsRequest):
    """
    Automatically analyzes event data to uncover trends, anomalies, and key takeaways.
    """
    return service.generate_insights(request)


@router.post(
    "/reporting/benchmarking",
    response_model=BenchmarkingResponse,
    tags=["Advanced Analytics & Reporting"],
)
def get_benchmarking_report(request: BenchmarkingRequest):
    """Compares event performance against historical data and industry standards."""
    return service.get_benchmarks(request)

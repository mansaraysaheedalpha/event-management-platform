from fastapi import APIRouter
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/intelligence/cultural-adaptation",
    response_model=CulturalAdaptationResponse,
    tags=["Global Intelligence"],
)
def get_cultural_adaptation(request: CulturalAdaptationRequest):
    """Adapts content to local customs and preferences."""
    return service.adapt_for_culture(request)


@router.post(
    "/intelligence/market-analysis",
    response_model=MarketAnalysisResponse,
    tags=["Global Intelligence"],
)
def get_market_analysis(request: MarketAnalysisRequest):
    """Provides global event industry insights and analysis."""
    return service.analyze_market(request)


@router.post(
    "/intelligence/competitive-analysis",
    response_model=CompetitiveAnalysisResponse,
    tags=["Global Intelligence"],
)
def get_competitive_analysis(request: CompetitiveAnalysisRequest):
    """Provides competitive intelligence and strategy analysis."""
    return service.analyze_competitors(request)

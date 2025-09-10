# app/features/intelligence/router.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from .schemas import *
from . import service

router = APIRouter()


@router.post(
    "/intelligence/cultural-adaptation",
    response_model=CulturalAdaptationResponse,
    tags=["Global Intelligence"],
)
def get_cultural_adaptation(
    request: CulturalAdaptationRequest, db: Session = Depends(get_db)
):
    """Adapts content to local customs and preferences."""
    return service.adapt_for_culture(db, request)


@router.post(
    "/intelligence/market-analysis",
    response_model=MarketAnalysisResponse,
    tags=["Global Intelligence"],
)
def get_market_analysis(request: MarketAnalysisRequest, db: Session = Depends(get_db)):
    """Provides global event industry insights and analysis."""
    return service.analyze_market(db, request)


@router.post(
    "/intelligence/competitive-analysis",
    response_model=CompetitiveAnalysisResponse,
    tags=["Global Intelligence"],
)
def get_competitive_analysis(
    request: CompetitiveAnalysisRequest, db: Session = Depends(get_db)
):
    """Provides competitive intelligence and strategy analysis."""
    return service.analyze_competitors(db, request)

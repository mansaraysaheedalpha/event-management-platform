# app/features/intelligence/service.py
from sqlalchemy.orm import Session
from app.db import crud
from .schemas import *


def adapt_for_culture(
    db: Session, request: CulturalAdaptationRequest
) -> CulturalAdaptationResponse:
    culture_data = crud.get_kb_entry(
        db, category="cultural_rules", key=request.target_culture
    )
    adapted_text = request.content_text
    for original, replacement in culture_data.get("replacements", {}).items():
        adapted_text = adapted_text.replace(original, replacement)
    return CulturalAdaptationResponse(
        adapted_text=adapted_text,
        sensitivities=culture_data.get("sensitivities", []),
        local_customs=culture_data.get("customs", []),
    )


def analyze_market(
    db: Session, request: MarketAnalysisRequest
) -> MarketAnalysisResponse:
    market_data = crud.get_kb_entry(
        db, category="market_data", key=f"{request.geographic_focus}_{request.industry}"
    )
    if not market_data:
        return MarketAnalysisResponse(
            market_size_usd_millions=0, growth_rate=0, key_segments=[]
        )
    return MarketAnalysisResponse(**market_data)


def analyze_competitors(
    db: Session, request: CompetitiveAnalysisRequest
) -> CompetitiveAnalysisResponse:
    profiles = []
    for competitor_name in request.target_competitors:
        data = crud.get_kb_entry(db, category="competitors", key=competitor_name)
        if data:
            profiles.append(
                CompetitiveAnalysisResponse.CompetitorProfile(
                    competitor_name=competitor_name, **data
                )
            )
    return CompetitiveAnalysisResponse(competitor_profiles=profiles)

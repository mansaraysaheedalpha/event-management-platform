from pydantic import BaseModel
from typing import List, Optional


class CulturalAdaptationRequest(BaseModel):
    content_text: str
    target_culture: str  # e.g., "Japan", "Brazil"


class CulturalAdaptationResponse(BaseModel):
    adapted_text: str
    sensitivities: List[str]
    local_customs: List[str]


class MarketAnalysisRequest(BaseModel):
    industry: str
    geographic_focus: str


class MarketAnalysisResponse(BaseModel):
    market_size: float  # In millions USD
    growth_rate: float
    key_segments: List[str]


class CompetitiveAnalysisRequest(BaseModel):
    target_competitors: List[str]


class CompetitiveAnalysisResponse(BaseModel):
    class CompetitorProfile(BaseModel):
        competitor_name: str
        strengths: List[str]
        weaknesses: List[str]

    competitor_profiles: List[CompetitorProfile]

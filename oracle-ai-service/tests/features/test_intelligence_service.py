# tests/features/test_intelligence_service.py
import pytest
from app.features.intelligence.service import *
from app.features.intelligence.schemas import *


def test_adapt_for_culture_provides_correct_suggestions(mocker):
    request = CulturalAdaptationRequest(
        content_text="This is a bad idea.", target_culture="Japan"
    )
    mock_data = {
        "sensitivities": ["Avoid direct criticism."],
        "customs": ["Punctuality is valued."],
        "replacements": {"bad idea": "concern worth discussing"},
    }
    mock_db = mocker.patch(
        "app.features.intelligence.service.crud.get_kb_entry", return_value=mock_data
    )
    response = adapt_for_culture(
        db=None, request=request
    )  # db=None because it's mocked
    assert "Avoid direct criticism." in response.sensitivities
    assert "concern worth discussing" in response.adapted_text


def test_analyze_market_retrieves_correct_data(mocker):
    request = MarketAnalysisRequest(industry="Tech", geographic_focus="Germany")
    mock_data = {
        "market_size_usd_millions": 150000,
        "growth_rate": 0.06,
        "key_segments": ["Cloud Computing"],
    }
    mock_db = mocker.patch(
        "app.features.intelligence.service.crud.get_kb_entry", return_value=mock_data
    )
    response = analyze_market(db=None, request=request)
    assert response.market_size_usd_millions == 150000


def test_analyze_competitors_retrieves_profiles(mocker):
    request = CompetitiveAnalysisRequest(target_competitors=["EventCorp"])
    mock_data = {
        "strengths": ["Strong brand recognition"],
        "weaknesses": ["Less agile"],
    }
    mock_db = mocker.patch(
        "app.features.intelligence.service.crud.get_kb_entry", return_value=mock_data
    )
    response = analyze_competitors(db=None, request=request)
    assert len(response.competitor_profiles) == 1
    assert "Less agile" in response.competitor_profiles[0].weaknesses

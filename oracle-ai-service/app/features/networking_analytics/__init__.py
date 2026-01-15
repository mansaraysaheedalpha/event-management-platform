# app/features/networking_analytics/__init__.py
"""
Networking Analytics feature for organizer dashboards.

Provides metrics on:
- Profile enrichment rates
- Recommendation engagement
- Connection metrics
- Huddle performance
- Top matching factors
"""

from app.features.networking_analytics.router import router
from app.features.networking_analytics.schemas import (
    NetworkingAnalyticsResponse,
    AnalyticsExportResponse,
)
from app.features.networking_analytics.service import NetworkingAnalyticsService

__all__ = [
    "router",
    "NetworkingAnalyticsResponse",
    "AnalyticsExportResponse",
    "NetworkingAnalyticsService",
]

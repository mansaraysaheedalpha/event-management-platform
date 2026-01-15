# app/features/enrichment/schemas.py
"""API schemas for profile enrichment endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.profile_enrichment.schemas import (
    EnrichedProfile,
    EnrichmentStatus,
    ProfileTier,
)


class EnrichmentRequest(BaseModel):
    """Request to enrich a user's profile."""

    name: str = Field(..., min_length=1, max_length=200, description="User's full name")
    email: str = Field(..., max_length=320, description="User's email address")
    company: str = Field(..., min_length=1, max_length=200, description="User's company")
    role: str = Field(..., min_length=1, max_length=200, description="User's job role")
    linkedin_url: Optional[str] = Field(None, max_length=500, description="LinkedIn profile URL")
    github_username: Optional[str] = Field(None, max_length=100, description="GitHub username")
    twitter_handle: Optional[str] = Field(None, max_length=100, description="Twitter handle")


class EnrichmentResponse(BaseModel):
    """Response from enrichment request."""

    status: str = Field(..., description="Enrichment status: processing, completed, failed, opted_out, already_enriched")
    message: str = Field(..., description="Human-readable status message")
    task_id: Optional[str] = Field(None, description="Background task ID for tracking")
    profile_tier: Optional[str] = Field(None, description="Assigned profile tier if completed")
    sources_found: Optional[list[str]] = Field(None, description="Sources found during enrichment")


class EnrichmentStatusResponse(BaseModel):
    """Response for enrichment status check."""

    user_id: str = Field(..., description="User identifier")
    status: EnrichmentStatus = Field(..., description="Current enrichment status")
    profile_tier: Optional[ProfileTier] = Field(None, description="Profile tier if enriched")
    enriched_at: Optional[datetime] = Field(None, description="When enrichment completed")
    sources: list[str] = Field(default_factory=list, description="Sources found")
    enriched_profile: Optional[EnrichedProfile] = Field(None, description="Enriched profile data")


class EnrichmentStatsResponse(BaseModel):
    """Statistics about enrichment service."""

    total_enrichments: int = Field(..., description="Total enrichment attempts")
    successful_enrichments: int = Field(..., description="Successful enrichments")
    failed_enrichments: int = Field(..., description="Failed enrichments")
    success_rate: float = Field(..., description="Success rate percentage")
    tier_distribution: dict[str, int] = Field(..., description="Distribution by tier")
    avg_processing_time_seconds: float = Field(..., description="Average processing time")


class BatchEnrichmentRequest(BaseModel):
    """Request to enrich multiple users (for events)."""

    event_id: str = Field(..., description="Event identifier")
    attendees: list[dict] = Field(..., description="List of attendee data")


class BatchEnrichmentResponse(BaseModel):
    """Response from batch enrichment request."""

    event_id: str
    queued: int = Field(..., description="Number of enrichments queued")
    skipped: int = Field(..., description="Number of already-processed users skipped")
    total: int = Field(..., description="Total attendees in request")
    message: str

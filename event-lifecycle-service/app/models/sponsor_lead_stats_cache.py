# app/models/sponsor_lead_stats_cache.py
"""
SponsorLeadStatsCache model - Pre-computed lead statistics per sponsor.

This table is automatically maintained by a PostgreSQL trigger that updates
stats whenever leads are inserted, updated, or deleted. This eliminates the
need to run expensive aggregation queries on every dashboard load.

Benefits:
- O(1) stats retrieval instead of O(n) aggregation
- Consistent metrics across all dashboard views
- Real-time updates via database trigger
- No external dependencies (Redis optional enhancement)
"""

import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Numeric, ForeignKey, text, UniqueConstraint
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SponsorLeadStatsCache(Base):
    __tablename__ = "sponsor_lead_stats_cache"

    id = Column(
        String, primary_key=True, default=lambda: f"slsc_{uuid.uuid4().hex[:12]}"
    )
    sponsor_id = Column(String, ForeignKey("sponsors.id", ondelete="CASCADE"), nullable=False, index=True)
    event_id = Column(String, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)

    # Lead counts by intent level
    total_leads = Column(Integer, nullable=False, server_default=text("0"))
    hot_leads = Column(Integer, nullable=False, server_default=text("0"))
    warm_leads = Column(Integer, nullable=False, server_default=text("0"))
    cold_leads = Column(Integer, nullable=False, server_default=text("0"))

    # Follow-up tracking
    leads_contacted = Column(Integer, nullable=False, server_default=text("0"))
    leads_converted = Column(Integer, nullable=False, server_default=text("0"))
    conversion_rate = Column(Numeric(5, 2), nullable=False, server_default=text("0"))

    # Scoring metrics
    avg_intent_score = Column(Numeric(5, 1), nullable=False, server_default=text("0"))
    max_intent_score = Column(Integer, nullable=False, server_default=text("0"))
    min_intent_score = Column(Integer, nullable=False, server_default=text("0"))

    # Engagement metrics
    total_interactions = Column(Integer, nullable=False, server_default=text("0"))
    avg_interactions_per_lead = Column(Numeric(5, 2), nullable=False, server_default=text("0"))

    # Timestamps
    last_lead_at = Column(DateTime(timezone=True), nullable=True)
    calculated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    # Unique constraint to ensure one cache record per sponsor per event
    __table_args__ = (
        UniqueConstraint('sponsor_id', 'event_id', name='uq_lead_stats_sponsor_event'),
    )

    # Relationships
    sponsor = relationship("Sponsor", back_populates="lead_stats_cache")

    def to_dict(self) -> dict:
        """Convert stats to dictionary for API response."""
        return {
            'total_leads': self.total_leads,
            'hot_leads': self.hot_leads,
            'warm_leads': self.warm_leads,
            'cold_leads': self.cold_leads,
            'leads_contacted': self.leads_contacted,
            'leads_converted': self.leads_converted,
            'conversion_rate': float(self.conversion_rate) if self.conversion_rate else 0,
            'avg_intent_score': float(self.avg_intent_score) if self.avg_intent_score else 0,
            'max_intent_score': self.max_intent_score,
            'min_intent_score': self.min_intent_score,
            'total_interactions': self.total_interactions,
            'avg_interactions_per_lead': float(self.avg_interactions_per_lead) if self.avg_interactions_per_lead else 0,
            'last_lead_at': self.last_lead_at.isoformat() if self.last_lead_at else None,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None,
        }

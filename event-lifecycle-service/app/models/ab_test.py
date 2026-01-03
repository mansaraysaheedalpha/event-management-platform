# app/models/ab_test.py
import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Integer, JSON, CheckConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from app.db.base_class import Base


class ABTest(Base):
    """
    A/B test configuration model.

    Stores test definitions that can be referenced by the frontend.
    Tests can be activated/deactivated and configured from the backend.
    """
    __tablename__ = "ab_tests"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Test identification
    test_id = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "checkout_button_color"
    name = Column(String(255), nullable=False)  # Human-readable name
    description = Column(String, nullable=True)  # Test description

    # Event association
    event_id = Column(String, nullable=False, index=True)  # Which event this test applies to

    # Test configuration
    variants = Column(JSON, nullable=False)  # Array of variant objects: [{ id, name, weight }]

    # Status
    is_active = Column(Boolean, nullable=False, server_default=text("false"))

    # Targeting (optional)
    target_audience = Column(JSON, nullable=True)  # { segments: [], ticket_tiers: [] }

    # Metrics to track
    goal_metric = Column(String(100), nullable=False)  # e.g., "purchase_conversion"
    secondary_metrics = Column(JSON, nullable=True)  # Array of additional metrics to track

    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    started_at = Column(DateTime(timezone=True), nullable=True)  # When test was activated
    ended_at = Column(DateTime(timezone=True), nullable=True)  # When test was deactivated

    # Minimum sample size before declaring winner
    min_sample_size = Column(Integer, nullable=False, server_default=text("100"))

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "goal_metric IN ('click_through', 'purchase_conversion', 'signup_conversion', 'engagement_time', 'custom')",
            name="valid_goal_metric"
        ),
    )


class ABTestEvent(Base):
    """
    Records user interactions with A/B test variants.

    Used for:
    - Tracking which variant each user saw
    - Recording goal conversions
    - Calculating variant performance
    - Statistical significance analysis
    """
    __tablename__ = "ab_test_events"

    id = Column(PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))

    # Test reference
    test_id = Column(String(100), nullable=False, index=True)  # References ABTest.test_id
    event_id = Column(String, nullable=False, index=True)  # Event ID

    # User tracking
    user_id = Column(String, nullable=True, index=True)  # Nullable for anonymous users
    session_token = Column(String(255), nullable=False, index=True)  # Frontend session ID

    # Variant assignment
    variant_id = Column(String(100), nullable=False, index=True)  # Which variant user saw

    # Event type
    event_type = Column(String(50), nullable=False, index=True)

    # Goal conversion tracking
    goal_achieved = Column(Boolean, nullable=False, server_default=text("false"))
    goal_value = Column(Integer, nullable=True)  # Optional value (e.g., revenue cents)

    # Context
    context = Column(JSON, nullable=True)  # Additional event data

    # Technical data
    user_agent = Column(String(500), nullable=True)  # Limited to 500 chars for security

    # Timestamp
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"), index=True)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('variant_view', 'goal_conversion', 'secondary_metric')",
            name="valid_event_type"
        ),
    )

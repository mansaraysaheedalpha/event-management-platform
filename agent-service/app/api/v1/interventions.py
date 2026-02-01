"""
Interventions API Endpoints
Provides manual intervention triggers and history viewing

SECURITY: All endpoints require authentication and verify user permissions
"""
import logging
from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import uuid

from app.db.timescale import get_db
from app.db.models import Intervention
from app.agents.intervention_selector import intervention_selector, InterventionRecommendation
from app.agents.intervention_executor import InterventionExecutor
from app.core.redis_client import redis_client
from app.middleware.auth import verify_token, verify_organizer, AuthUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/interventions", tags=["interventions"])


# Pydantic models
class ManualInterventionRequest(BaseModel):
    """Request to manually trigger an intervention"""
    session_id: str = Field(..., description="Session ID")
    event_id: str = Field(..., description="Event ID")
    intervention_type: str = Field(..., description="Type of intervention (POLL, CHAT_PROMPT, NOTIFICATION)")
    reason: str = Field(..., description="Reason for manual intervention")
    context: dict = Field(default_factory=dict, description="Additional context")


class InterventionResponse(BaseModel):
    """Response for intervention request"""
    success: bool
    intervention_id: Optional[str] = None
    message: str
    details: Optional[dict] = None


class InterventionHistoryItem(BaseModel):
    """Single intervention history item"""
    id: str
    session_id: str
    timestamp: datetime
    type: str
    confidence: float
    reasoning: Optional[str] = None
    outcome: Optional[dict] = None
    metadata: Optional[dict] = None


class InterventionHistoryResponse(BaseModel):
    """Response containing intervention history"""
    total: int
    interventions: List[InterventionHistoryItem]


@router.post("/manual", response_model=InterventionResponse)
async def trigger_manual_intervention(
    request: ManualInterventionRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(verify_organizer)  # Authentication required
):
    """
    Manually trigger an intervention for a session.

    This endpoint allows organizers to manually trigger interventions
    without waiting for anomaly detection.

    **Authentication Required**: Must be event organizer
    """
    try:
        logger.info(
            f"🎯 Manual intervention requested by user {user.sub}: {request.intervention_type} "
            f"for session {request.session_id[:8]}..."
        )

        # Create intervention recommendation
        recommendation = InterventionRecommendation(
            intervention_type=request.intervention_type,
            priority='HIGH',
            confidence=1.0,  # Manual interventions have max confidence
            reason=f"Manual trigger: {request.reason}",
            context={
                'session_id': request.session_id,
                'event_id': request.event_id,
                'manual': True,
                'triggered_by': user.sub,
                **request.context
            },
            estimated_impact=0.0  # Unknown for manual interventions
        )

        # Execute intervention (InterventionExecutor handles redis_client internally)
        executor = InterventionExecutor()
        result = await executor.execute(
            recommendation=recommendation,
            db_session=db,
            session_context=request.context
        )

        if result['success']:
            return InterventionResponse(
                success=True,
                intervention_id=result.get('intervention_id'),
                message=f"{request.intervention_type} intervention triggered successfully",
                details=result
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to execute intervention: {result.get('error', 'Unknown error')}"
            )

    except Exception as e:
        logger.error(f"Manual intervention failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


@router.get("/history/{session_id}", response_model=InterventionHistoryResponse)
async def get_intervention_history(
    session_id: str,
    limit: int = Query(default=50, le=200, description="Maximum number of interventions to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(verify_organizer)  # Authentication required
):
    """
    Get intervention history for a session.

    Returns a list of all interventions that were triggered for the specified session.

    **Authentication Required**: Must be event organizer
    """
    try:
        # Query interventions (session_id is now a string, not UUID)
        stmt = (
            select(Intervention)
            .where(Intervention.session_id == session_id)
            .order_by(desc(Intervention.timestamp))
            .limit(limit)
            .offset(offset)
        )

        result = await db.execute(stmt)
        interventions = result.scalars().all()

        # Count total
        from sqlalchemy import func
        count_stmt = (
            select(func.count())
            .select_from(Intervention)
            .where(Intervention.session_id == session_id)
        )
        total_result = await db.execute(count_stmt)
        total = total_result.scalar()

        # Convert to response model
        history_items = [
            InterventionHistoryItem(
                id=str(i.id),
                session_id=i.session_id,
                timestamp=i.timestamp,
                type=i.type,
                confidence=i.confidence,
                reasoning=i.reasoning,
                outcome=i.outcome,
                metadata=i.metadata
            )
            for i in interventions
        ]

        return InterventionHistoryResponse(
            total=total or 0,
            interventions=history_items
        )

    except Exception as e:
        logger.error(f"Failed to fetch intervention history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/event/{event_id}", response_model=InterventionHistoryResponse)
async def get_event_intervention_history(
    event_id: str,
    hours: int = Query(default=24, le=168, description="Look back hours (max 1 week)"),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(verify_organizer)  # Authentication required
):
    """
    Get intervention history for all sessions in an event.

    Returns interventions from the past N hours for the specified event.

    **Authentication Required**: Must be event organizer
    """
    try:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        # Query interventions for this event
        # Note: This requires joining with engagement_metrics to get event_id
        # For now, we'll use metadata field which should contain event_id
        from sqlalchemy import and_, cast, String
        from sqlalchemy.dialects.postgresql import JSONB

        stmt = (
            select(Intervention)
            .where(
                and_(
                    Intervention.timestamp >= cutoff_time,
                    cast(Intervention.metadata['event_id'], String) == event_id
                )
            )
            .order_by(desc(Intervention.timestamp))
            .limit(limit)
        )

        result = await db.execute(stmt)
        interventions = result.scalars().all()

        # Convert to response model
        history_items = [
            InterventionHistoryItem(
                id=str(i.id),
                session_id=str(i.session_id),
                timestamp=i.timestamp,
                type=i.type,
                confidence=i.confidence,
                reasoning=i.reasoning,
                outcome=i.outcome,
                metadata=i.metadata
            )
            for i in interventions
        ]

        return InterventionHistoryResponse(
            total=len(history_items),
            interventions=history_items
        )

    except Exception as e:
        logger.error(f"Failed to fetch event intervention history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{session_id}")
async def get_intervention_stats(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(verify_organizer)  # Authentication required
):
    """
    Get intervention statistics for a session.

    Returns counts by type, success rate, and effectiveness metrics.

    **Authentication Required**: Must be event organizer
    """
    try:
        # Query all interventions for session (session_id is now a string)
        stmt = select(Intervention).where(Intervention.session_id == session_id)
        result = await db.execute(stmt)
        interventions = result.scalars().all()

        if not interventions:
            return {
                'session_id': session_id,
                'total_interventions': 0,
                'by_type': {},
                'success_rate': 0.0,
                'avg_confidence': 0.0
            }

        # Calculate stats
        by_type = {}
        successful = 0
        total_confidence = 0.0

        for intervention in interventions:
            # Count by type
            by_type[intervention.type] = by_type.get(intervention.type, 0) + 1

            # Count successes
            if intervention.outcome and intervention.outcome.get('success'):
                successful += 1

            # Sum confidence
            total_confidence += intervention.confidence

        success_rate = successful / len(interventions) if interventions else 0.0
        avg_confidence = total_confidence / len(interventions) if interventions else 0.0

        return {
            'session_id': session_id,
            'total_interventions': len(interventions),
            'by_type': by_type,
            'success_rate': round(success_rate, 3),
            'avg_confidence': round(avg_confidence, 3),
            'successful_interventions': successful
        }

    except Exception as e:
        logger.error(f"Failed to calculate intervention stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

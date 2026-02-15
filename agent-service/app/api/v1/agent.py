"""
Agent Orchestrator API Endpoints
Handles agent mode changes, status queries, and session registration

SECURITY: All endpoints require authentication and verify user permissions
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

from app.orchestrator import agent_manager
from app.middleware import AppError, ErrorCategory
from app.middleware.auth import verify_token, verify_organizer, AuthUser
from app.agents.engagement_conductor import AgentMode
from app.db.timescale import AsyncSessionLocal
from app.models.event_agent_settings import EventAgentSettings
from app.core.event_settings import get_event_settings_loader
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()


def validate_uuid(value: str, field_name: str = "id") -> str:
    """
    Validate that a string is a valid UUID.

    Args:
        value: String to validate
        field_name: Name of the field for error messages

    Returns:
        The validated UUID string

    Raises:
        AppError: If the string is not a valid UUID
    """
    try:
        uuid.UUID(value)
        return value
    except ValueError:
        raise AppError(
            message=f"Invalid {field_name} format: '{value}' is not a valid UUID",
            category=ErrorCategory.VALIDATION,
            status_code=400
        )


# Request/Response Models
class AgentModeChangeRequest(BaseModel):
    """Request to change agent operating mode"""
    mode: Literal["MANUAL", "SEMI_AUTO", "AUTO"] = Field(
        ...,
        description="Agent operating mode"
    )


class AgentStatusResponse(BaseModel):
    """Current agent status"""
    session_id: str
    mode: str
    status: str
    last_activity: Optional[str] = None
    confidence_score: Optional[float] = None
    current_decision: Optional[dict] = None
    is_active: bool


class SessionRegistrationRequest(BaseModel):
    """Register a session with the agent orchestrator"""
    event_id: str
    session_id: str
    metadata: Optional[dict] = None


class SessionRegistrationResponse(BaseModel):
    """Session registration result"""
    session_id: str
    event_id: str
    agent_mode: str
    registered_at: str
    message: str


# Endpoints

def extract_event_id_from_session(session_id: str) -> str:
    """
    Extract event_id from various session_id formats.

    Supported formats:
    - event_{event_id}_{stream_id} -> event_id
    - {uuid} (database session ID) -> uses session_id as-is for event_id lookup
    - evt_{event_id} -> event_id portion

    Returns the event_id or the session_id itself if no extraction pattern matches.
    """
    # Format: event_{event_id}_{stream_id}
    if session_id.startswith("event_"):
        parts = session_id.split("_")
        if len(parts) >= 3:
            return "_".join(parts[1:-1])
        return parts[1] if len(parts) > 1 else session_id

    # Format: evt_{event_id}
    if session_id.startswith("evt_"):
        return session_id[4:]

    # UUID format or other - return as-is
    # The agent manager will use this as both session_id and event_id reference
    return session_id


@router.put("/agent/sessions/{session_id}/mode")
async def change_agent_mode(
    session_id: str,
    request: AgentModeChangeRequest,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Authentication required
):
    """
    Change the agent operating mode for a session

    🔒 **Authentication Required**: Must be event organizer

    Modes:
    - MANUAL: Agent only suggests, requires human approval for all interventions
    - SEMI_AUTO: Agent auto-executes high-confidence decisions, asks for low-confidence
    - AUTO: Agent fully autonomous, auto-executes all decisions

    Supported session_id formats:
    - event_{event_id}_{stream_id} (legacy format)
    - {uuid} (database session ID)
    - evt_{event_id}

    Note: If session doesn't exist, it will be auto-created with the specified mode
    """
    try:
        # Get agent instance for session
        agent = agent_manager.get_agent(session_id)

        # Auto-create agent if it doesn't exist
        if not agent:
            # Extract event_id from session_id (supports multiple formats)
            event_id = extract_event_id_from_session(session_id)

            # Create agent instance
            agent = await agent_manager.create_agent(
                session_id=session_id,
                event_id=event_id,
                metadata={"auto_created": True, "created_by": "mode_change"}
            )

        # Change mode on both the agent instance AND the orchestrator config
        # agent.set_mode() only updates agent._current_mode (not used by run_agent)
        # agent_manager.set_agent_mode() updates config.agent_mode (used by run_agent)
        new_mode = AgentMode(request.mode)
        await agent.set_mode(new_mode)
        agent_manager.set_agent_mode(session_id, new_mode)

        # Persist mode to database so it survives service restarts
        # and is read correctly by signal_collector._get_event_agent_mode()
        event_id = agent_manager.configs[session_id].event_id if session_id in agent_manager.configs else extract_event_id_from_session(session_id)
        try:
            async with AsyncSessionLocal() as db:
                stmt = select(EventAgentSettings).where(EventAgentSettings.event_id == event_id)
                result = await db.execute(stmt)
                settings = result.scalar_one_or_none()

                if settings:
                    settings.agent_mode = request.mode
                    settings.updated_at = datetime.now(timezone.utc)
                else:
                    settings = EventAgentSettings(
                        event_id=event_id,
                        agent_mode=request.mode,
                        agent_enabled=True,
                    )
                    db.add(settings)

                await db.commit()

            # Invalidate cached settings so next read picks up new mode
            get_event_settings_loader().invalidate(event_id)
            logger.info(f"Persisted agent mode {request.mode} for event {event_id}")
        except Exception as e:
            logger.warning(f"Failed to persist mode to DB (in-memory change still applied): {e}")

        return {
            "session_id": session_id,
            "mode": request.mode,
            "changed_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Agent mode changed to {request.mode}"
        }

    except AppError:
        raise
    except Exception as e:
        # Log full error for debugging, return sanitized message to client
        logger.error(f"Failed to change agent mode for session {session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to change agent mode. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.get("/agent/sessions/{session_id}/status", response_model=AgentStatusResponse)
async def get_agent_status(
    session_id: str,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Authentication required
):
    """
    Get current agent status for a session

    🔒 **Authentication Required**: Must be event organizer

    Returns:
    - Agent mode (MANUAL/SEMI_AUTO/AUTO)
    - Current status (MONITORING/ANALYZING/INTERVENING/etc)
    - Last activity timestamp
    - Current decision (if any)
    - Confidence score (if making a decision)
    """
    try:
        # Get agent instance
        agent = agent_manager.get_agent(session_id)

        if not agent:
            # Return inactive status if no agent running
            return AgentStatusResponse(
                session_id=session_id,
                mode="MANUAL",
                status="IDLE",
                is_active=False
            )

        # Get agent state
        state = await agent.get_state()

        return AgentStatusResponse(
            session_id=session_id,
            mode=state.get("mode", "MANUAL"),
            status=state.get("status", "MONITORING"),
            last_activity=state.get("last_activity"),
            confidence_score=state.get("confidence_score"),
            current_decision=state.get("current_decision"),
            is_active=True
        )

    except Exception as e:
        logger.error(f"Failed to get agent status for session {session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to get agent status. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.post("/agent/sessions/register", response_model=SessionRegistrationResponse)
async def register_session(
    request: SessionRegistrationRequest,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Organizer required (HIGH-12 fix)
):
    """
    Register a session with the agent orchestrator

    🔒 **Authentication Required**: Must be event organizer

    This starts an agent instance for the session that will:
    - Monitor engagement signals
    - Detect anomalies
    - Suggest/execute interventions based on mode

    Note: Typically called automatically by signal collector, but can be manually triggered.
    """
    try:
        # Register session with agent manager
        agent = await agent_manager.create_agent(
            session_id=request.session_id,
            event_id=request.event_id,
            metadata=request.metadata or {}
        )

        return SessionRegistrationResponse(
            session_id=request.session_id,
            event_id=request.event_id,
            agent_mode="MANUAL",  # Default mode
            registered_at=datetime.now(timezone.utc).isoformat(),
            message=f"Session {request.session_id} registered with agent orchestrator"
        )

    except Exception as e:
        logger.error(f"Failed to register session {request.session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to register session. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.delete("/agent/sessions/{session_id}")
async def unregister_session(
    session_id: str,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Authentication required
):
    """
    Unregister a session from the agent orchestrator

    🔒 **Authentication Required**: Must be event organizer

    This stops the agent instance and cleans up resources
    """
    try:
        # Stop and remove agent
        await agent_manager.remove_agent(session_id)

        return {
            "session_id": session_id,
            "unregistered_at": datetime.now(timezone.utc).isoformat(),
            "message": f"Session {session_id} unregistered from agent orchestrator"
        }

    except Exception as e:
        logger.error(f"Failed to unregister session {session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to unregister session. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.post("/agent/sessions/{session_id}/decisions/{decision_id}/approve")
async def approve_decision(
    session_id: str,
    decision_id: str,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Authentication required
):
    """
    Approve a pending agent decision (for MANUAL and SEMI_AUTO modes)

    🔒 **Authentication Required**: Must be event organizer

    This triggers the agent to execute the intervention
    """
    try:
        # Validate decision_id is a valid UUID
        validate_uuid(decision_id, "decision_id")

        agent = agent_manager.get_agent(session_id)

        if not agent:
            raise AppError(
                message=f"No active agent found for session {session_id}",
                category=ErrorCategory.NOT_FOUND,
                status_code=404
            )

        # Approve and execute decision
        result = await agent.approve_decision(decision_id)

        return {
            "session_id": session_id,
            "decision_id": decision_id,
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "execution_result": result,
            "message": "Decision approved and executed"
        }

    except AppError:
        raise
    except Exception as e:
        logger.error(f"Failed to approve decision {decision_id} for session {session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to approve decision. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.post("/agent/sessions/{session_id}/decisions/{decision_id}/reject")
async def reject_decision(
    session_id: str,
    decision_id: str,
    reason: Optional[str] = None,
    user: AuthUser = Depends(verify_organizer)  # 🔒 Authentication required
):
    """
    Reject a pending agent decision

    🔒 **Authentication Required**: Must be event organizer

    This discards the suggestion and provides feedback to the learning system
    """
    try:
        # Validate decision_id is a valid UUID
        validate_uuid(decision_id, "decision_id")

        agent = agent_manager.get_agent(session_id)

        if not agent:
            raise AppError(
                message=f"No active agent found for session {session_id}",
                category=ErrorCategory.NOT_FOUND,
                status_code=404
            )

        # Reject decision and record feedback
        await agent.reject_decision(decision_id, reason=reason)

        return {
            "session_id": session_id,
            "decision_id": decision_id,
            "rejected_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "message": "Decision rejected"
        }

    except AppError:
        raise
    except Exception as e:
        logger.error(f"Failed to reject decision {decision_id} for session {session_id}: {e}", exc_info=True)
        raise AppError(
            message="Failed to reject decision. Please try again.",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )

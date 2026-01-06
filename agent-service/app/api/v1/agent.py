"""
Agent Orchestrator API Endpoints
Handles agent mode changes, status queries, and session registration

SECURITY: All endpoints require authentication and verify user permissions
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

from app.orchestrator import agent_manager
from app.middleware import AppError, ErrorCategory
from app.middleware.auth import verify_token, verify_organizer, AuthUser

router = APIRouter()


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
    """
    try:
        # Get agent instance for session
        agent = agent_manager.get_agent(session_id)

        if not agent:
            raise AppError(
                message=f"No active agent found for session {session_id}",
                category=ErrorCategory.NOT_FOUND,
                status_code=404
            )

        # Change mode
        await agent.set_mode(request.mode)

        return {
            "session_id": session_id,
            "mode": request.mode,
            "changed_at": datetime.utcnow().isoformat(),
            "message": f"Agent mode changed to {request.mode}"
        }

    except AppError:
        raise
    except Exception as e:
        raise AppError(
            message=f"Failed to change agent mode: {str(e)}",
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
        raise AppError(
            message=f"Failed to get agent status: {str(e)}",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )


@router.post("/agent/sessions/register", response_model=SessionRegistrationResponse)
async def register_session(
    request: SessionRegistrationRequest,
    user: AuthUser = Depends(verify_token)  # 🔒 Authentication required
):
    """
    Register a session with the agent orchestrator

    🔒 **Authentication Required**: Must be authenticated user

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
            registered_at=datetime.utcnow().isoformat(),
            message=f"Session {request.session_id} registered with agent orchestrator"
        )

    except Exception as e:
        raise AppError(
            message=f"Failed to register session: {str(e)}",
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
            "unregistered_at": datetime.utcnow().isoformat(),
            "message": f"Session {session_id} unregistered from agent orchestrator"
        }

    except Exception as e:
        raise AppError(
            message=f"Failed to unregister session: {str(e)}",
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
            "approved_at": datetime.utcnow().isoformat(),
            "execution_result": result,
            "message": "Decision approved and executed"
        }

    except AppError:
        raise
    except Exception as e:
        raise AppError(
            message=f"Failed to approve decision: {str(e)}",
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
            "rejected_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "message": "Decision rejected"
        }

    except AppError:
        raise
    except Exception as e:
        raise AppError(
            message=f"Failed to reject decision: {str(e)}",
            category=ErrorCategory.INTERNAL,
            status_code=500
        )

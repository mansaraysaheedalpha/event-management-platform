"""
Test Endpoints for Agent Development & Testing

These endpoints allow you to manually trigger agent behaviors
to test the full integration without waiting for real engagement drops.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

from app.orchestrator import agent_manager
from app.agents.engagement_conductor import AgentMode
from app.models.anomaly import Anomaly, AnomalyType, AnomalySeverity

router = APIRouter()


class TriggerAgentRequest(BaseModel):
    """Request to manually trigger agent execution"""
    session_id: str = Field(..., description="Session ID to run agent for")
    event_id: str = Field(..., description="Event ID")

    # Current state
    engagement_score: float = Field(45.0, ge=0.0, le=100.0, description="Current engagement score")
    active_users: int = Field(50, ge=0, description="Number of active users")

    # Simulate anomaly
    simulate_anomaly: bool = Field(True, description="Whether to simulate an anomaly")
    anomaly_type: str = Field("DROP", description="Type of anomaly (DROP, SPIKE, PLATEAU)")
    anomaly_severity: str = Field("HIGH", description="Severity (LOW, MEDIUM, HIGH, CRITICAL)")

    # Agent mode
    agent_mode: str = Field("MANUAL", description="Agent mode (MANUAL, SEMI_AUTO, AUTO)")


class SimulateEngagementDropRequest(BaseModel):
    """Request to simulate an engagement drop scenario"""
    session_id: str
    event_id: str
    initial_score: float = Field(75.0, ge=0.0, le=100.0)
    drop_to_score: float = Field(45.0, ge=0.0, le=100.0)
    active_users: int = Field(100, ge=0)


@router.post("/test/trigger-agent")
async def trigger_agent(request: TriggerAgentRequest):
    """
    Manually trigger the agent to run for testing.

    This endpoint simulates the full agent cycle:
    1. Perceive - Check engagement signals
    2. Decide - Select intervention using Thompson Sampling
    3. Act - Execute intervention (or wait for approval)
    4. Learn - Update statistics

    Use this to test the agent without waiting for real engagement drops.
    """
    try:
        # Register session if not already registered
        if request.session_id not in agent_manager.configs:
            agent_manager.register_session(
                session_id=request.session_id,
                event_id=request.event_id,
                agent_mode=AgentMode(request.agent_mode)
            )

        # Create anomaly if requested
        anomaly = None
        if request.simulate_anomaly:
            anomaly = Anomaly(
                session_id=request.session_id,
                event_id=request.event_id,
                anomaly_type=request.anomaly_type,
                severity=request.anomaly_severity,
                detected_at=datetime.utcnow(),
                current_value=request.engagement_score,
                baseline_value=75.0,  # Simulated baseline
                deviation=30.0,  # Simulated deviation
                confidence=0.95,
                context={
                    "active_users": request.active_users,
                    "session_duration_minutes": 15,
                    "time_of_day": "afternoon"
                }
            )

        # Prepare signals
        signals = {
            "engagement_score": request.engagement_score,
            "active_users": request.active_users,
            "messages_per_minute": 5.2,
            "reactions_per_minute": 12.5,
            "poll_participation_rate": 0.35
        }

        # Session context
        session_context = {
            "session_id": request.session_id,
            "event_id": request.event_id,
            "session_name": "Test Session",
            "organizer_id": "test_organizer"
        }

        # Run agent
        final_state = await agent_manager.run_agent(
            session_id=request.session_id,
            engagement_score=request.engagement_score,
            active_users=request.active_users,
            signals=signals,
            anomaly=anomaly,
            session_context=session_context
        )

        if not final_state:
            raise HTTPException(
                status_code=500,
                detail="Agent failed to run. Check if agent is enabled for this session."
            )

        return {
            "success": True,
            "message": "Agent executed successfully",
            "result": {
                "session_id": request.session_id,
                "agent_mode": request.agent_mode,
                "status": final_state.get("status"),
                "anomaly_detected": final_state.get("anomaly_detected", False),
                "intervention_selected": final_state.get("selected_intervention").value if final_state.get("selected_intervention") else None,
                "confidence": final_state.get("confidence"),
                "requires_approval": final_state.get("requires_approval"),
                "approved": final_state.get("approved"),
                "intervention_id": final_state.get("intervention_id"),
                "success": final_state.get("success"),
                "explanation": final_state.get("explanation")
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger agent: {str(e)}"
        )


@router.post("/test/simulate-engagement-drop")
async def simulate_engagement_drop(request: SimulateEngagementDropRequest):
    """
    Simulate a realistic engagement drop scenario.

    This creates a drop from high engagement to low engagement,
    triggers the agent, and shows what intervention would be suggested.
    """
    try:
        # Register session
        if request.session_id not in agent_manager.configs:
            agent_manager.register_session(
                session_id=request.session_id,
                event_id=request.event_id,
                agent_mode=AgentMode.SEMI_AUTO  # Use semi-auto for realistic testing
            )

        # Create DROP anomaly
        drop_percentage = ((request.initial_score - request.drop_to_score) / request.initial_score) * 100

        anomaly = Anomaly(
            session_id=request.session_id,
            event_id=request.event_id,
            anomaly_type="DROP",
            severity="HIGH" if drop_percentage > 30 else "MEDIUM",
            detected_at=datetime.utcnow(),
            current_value=request.drop_to_score,
            baseline_value=request.initial_score,
            deviation=drop_percentage,
            confidence=0.92,
            context={
                "active_users": request.active_users,
                "drop_percentage": drop_percentage,
                "time_since_last_activity": 5.2
            }
        )

        # Prepare signals (simulating low engagement)
        signals = {
            "engagement_score": request.drop_to_score,
            "active_users": request.active_users,
            "messages_per_minute": 2.1,  # Low
            "reactions_per_minute": 3.5,  # Low
            "poll_participation_rate": 0.15  # Low
        }

        # Run agent
        final_state = await agent_manager.run_agent(
            session_id=request.session_id,
            engagement_score=request.drop_to_score,
            active_users=request.active_users,
            signals=signals,
            anomaly=anomaly,
            session_context={
                "session_id": request.session_id,
                "event_id": request.event_id,
                "session_name": "Demo Session"
            }
        )

        return {
            "success": True,
            "message": "Engagement drop simulated and agent triggered",
            "scenario": {
                "initial_score": request.initial_score,
                "dropped_to": request.drop_to_score,
                "drop_percentage": f"{drop_percentage:.1f}%",
                "severity": anomaly.severity
            },
            "agent_response": {
                "intervention_type": final_state.get("selected_intervention").value if final_state.get("selected_intervention") else None,
                "confidence": final_state.get("confidence"),
                "reasoning": final_state.get("explanation"),
                "requires_approval": final_state.get("requires_approval"),
                "status": final_state.get("status")
            }
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to simulate engagement drop: {str(e)}"
        )


@router.get("/test/agent-status/{session_id}")
async def get_test_agent_status(session_id: str):
    """
    Get current agent status for testing.

    Shows what the agent is currently doing for a session.
    """
    try:
        status = agent_manager.get_agent_status(session_id)

        if not status:
            return {
                "session_id": session_id,
                "registered": False,
                "message": "Session not registered with agent orchestrator"
            }

        return {
            "session_id": session_id,
            "registered": True,
            "status": status
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get agent status: {str(e)}"
        )


@router.post("/test/reset-agent/{session_id}")
async def reset_agent_session(session_id: str):
    """
    Reset agent state for a session (useful for testing).

    This clears pending approvals and resets the agent to monitoring state.
    """
    try:
        # Unregister and re-register to reset
        agent_manager.unregister_session(session_id)

        return {
            "success": True,
            "message": f"Agent state reset for session {session_id}",
            "session_id": session_id
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset agent: {str(e)}"
        )

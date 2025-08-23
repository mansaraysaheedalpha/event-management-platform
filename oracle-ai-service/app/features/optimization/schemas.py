# app/features/optimization/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional


class ScheduleOptimizationRequest(BaseModel):
    class SessionInput(BaseModel):
        session_id: str
        start_time: str  # Using str for simplicity, can be datetime
        end_time: str
        predicted_attendance: int
        room_id: str
        room_capacity: int

    event_id: str
    current_schedule: List[SessionInput]


class ScheduleOptimizationResponse(BaseModel):
    class ScheduleChange(BaseModel):
        session_id: str
        original_room_id: str
        recommended_room_id: str
        reason: str

    optimized_schedule: List[ScheduleChange]
    overall_improvement_score: float = Field(..., ge=0, le=1)


class CapacityManagementRequest(BaseModel):
    session_id: str
    current_capacity: int
    current_registrations: int


class CapacityManagementResponse(BaseModel):
    recommended_capacity: int
    overflow_probability: float


class ResourceAllocationRequest(BaseModel):
    class SessionRequirement(BaseModel):
        session_id: str
        priority: str = Field(..., examples=["critical", "high", "medium", "low"])
        required_skill: Optional[str] = None  # e.g., "AV_Tech"

    class StaffMember(BaseModel):
        staff_id: str
        skills: List[str] = []

    event_id: str
    sessions: List[SessionRequirement]
    staff: List[StaffMember]


class ResourceAllocationResponse(BaseModel):
    class StaffAssignment(BaseModel):
        staff_id: str
        assigned_session_id: str

    class UnstaffedSession(BaseModel):
        session_id: str
        reason: str

    staff_assignments: List[StaffAssignment]
    unstaffed_sessions: List[
        UnstaffedSession
    ]  # It's critical to report what *couldn't* be solved
    overall_efficiency: float  # e.g., percentage of sessions staffed

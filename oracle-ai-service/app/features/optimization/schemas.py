from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ScheduleOptimizationRequest(BaseModel):
    class SessionInput(BaseModel):
        session_id: str
        start_time: datetime
        end_time: datetime
        predicted_attendance: int
        room_capacity: int

    event_id: str
    current_schedule: List[SessionInput]


class ScheduleOptimizationResponse(BaseModel):
    class ScheduleChange(BaseModel):
        session_id: str
        original_start_time: datetime
        recommended_start_time: datetime
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
    event_id: str
    staff_count: int
    sessions_count: int


class ResourceAllocationResponse(BaseModel):
    class StaffAssignment(BaseModel):
        staff_id: str
        assigned_session_id: str

    staff_assignments: List[StaffAssignment]
    overall_efficiency: float

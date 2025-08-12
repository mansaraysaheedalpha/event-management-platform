import random
from app.features.optimization.schemas import (
    ScheduleOptimizationRequest,
    ScheduleOptimizationResponse,
    CapacityManagementRequest,
    CapacityManagementResponse,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
)
def optimize_schedule(
    request: ScheduleOptimizationRequest,
) -> ScheduleOptimizationResponse:
    """
    This service function contains the logic for optimizing an event schedule.
    In a real system, this would use a constraint satisfaction or optimization
    algorithm to resolve conflicts and improve attendee flow.

    For now, we return a hardcoded, realistic response.
    """
    optimized_schedule = []

    # Simulate finding a scheduling conflict to resolve
    if len(request.current_schedule) > 1:
        conflicting_session = request.current_schedule[1]
        optimized_schedule.append(
            ScheduleOptimizationResponse.ScheduleChange(
                session_id=conflicting_session.session_id,
                original_start_time=conflicting_session.start_time,
                recommended_start_time=conflicting_session.start_time.replace(hour=15),
                reason="Predicted attendance exceeds room capacity. Moved to a later slot with a larger room.",
            )
        )

    return ScheduleOptimizationResponse(
        optimized_schedule=optimized_schedule,
        overall_improvement_score=round(random.uniform(0.6, 0.9), 2),
    )


def manage_capacity(request: CapacityManagementRequest) -> CapacityManagementResponse:
    """Simulates predicting and managing session capacity."""
    overflow_prob = 0.0
    recommended_capacity = request.current_capacity

    # Simulate a high demand scenario
    if request.current_registrations > request.current_capacity * 0.9:
        overflow_prob = round(random.uniform(0.6, 0.95), 2)
        recommended_capacity = int(
            request.current_capacity * 1.2
        )  # Suggest 20% increase

    return CapacityManagementResponse(
        recommended_capacity=recommended_capacity, overflow_probability=overflow_prob
    )


def optimize_resources(
    request: ResourceAllocationRequest,
) -> ResourceAllocationResponse:
    """Simulates optimizing staff and resource allocation."""
    assignments = []
    # Simple simulation: assign first few staff to first few sessions
    for i in range(min(request.staff_count, request.sessions_count)):
        assignments.append(
            ResourceAllocationResponse.StaffAssignment(
                staff_id=f"staff_{i+1}", assigned_session_id=f"ses_{100+i}"
            )
        )

    return ResourceAllocationResponse(
        staff_assignments=assignments,
        overall_efficiency=round(random.uniform(0.8, 0.98), 2),
    )

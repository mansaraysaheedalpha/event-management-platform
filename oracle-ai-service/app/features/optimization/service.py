# app/features/optimization/service.py
from typing import List, Dict, Any
from .schemas import (
    ScheduleOptimizationRequest,
    ScheduleOptimizationResponse,
    CapacityManagementRequest,
    CapacityManagementResponse,
    ResourceAllocationRequest,
    ResourceAllocationResponse,
)


def _get_available_rooms_from_db(event_id: str) -> List[Dict[str, Any]]:
    """
    Simulates fetching all available rooms and their capacities for an event.
    """
    print(f"Simulating DB query for rooms in event: {event_id}")
    return [
        {"id": "room_A", "capacity": 75},
        {"id": "room_B", "capacity": 100},
        {"id": "room_C", "capacity": 150},
        {"id": "room_D", "capacity": 500},
        {"id": "workshop_1", "capacity": 40},
    ]


def optimize_schedule(
    request: ScheduleOptimizationRequest,
) -> ScheduleOptimizationResponse:
    """
    Finds and resolves schedule conflicts using a heuristic-based solver.
    Currently focused on solving overcrowding issues.
    """
    all_rooms = _get_available_rooms_from_db(request.event_id)
    suggested_changes = []

    # Get a list of rooms currently occupied in this timeslot
    occupied_room_ids = {s.room_id for s in request.current_schedule}

    for session in request.current_schedule:
        # Conflict detection: Is the session overcrowded?
        if session.predicted_attendance > session.room_capacity:
            # Find a suitable replacement room
            best_fit_room = None

            # Sort available rooms by capacity to find the smallest suitable one
            potential_rooms = sorted(all_rooms, key=lambda r: r["capacity"])

            for room in potential_rooms:
                # Is the room big enough?
                is_large_enough = room["capacity"] >= session.predicted_attendance
                # Is the room available?
                is_available = room["id"] not in occupied_room_ids

                if is_large_enough and is_available:
                    best_fit_room = room
                    break  # Since the list is sorted, the first one we find is the best fit

            if best_fit_room:
                change = ScheduleOptimizationResponse.ScheduleChange(
                    session_id=session.session_id,
                    original_room_id=session.room_id,
                    recommended_room_id=best_fit_room["id"],
                    reason=f"Predicted attendance ({session.predicted_attendance}) exceeds room capacity ({session.room_capacity}).",
                )
                suggested_changes.append(change)
                # Mark the new room as occupied for this solver pass
                occupied_room_ids.add(best_fit_room["id"])

    return ScheduleOptimizationResponse(
        optimized_schedule=suggested_changes,
        overall_improvement_score=(
            len(suggested_changes) / len(request.current_schedule)
            if request.current_schedule
            else 0
        ),
    )


def manage_capacity(request: CapacityManagementRequest) -> CapacityManagementResponse:
    """
    Predicts and manages session capacity using a heuristic model based on
    the current registration to capacity ratio.
    """
    # Avoid division by zero if capacity is 0
    if request.current_capacity == 0:
        return CapacityManagementResponse(
            recommended_capacity=10, overflow_probability=0.0
        )

    registration_ratio = request.current_registrations / request.current_capacity

    # --- Heuristic Risk Tiers ---
    if registration_ratio >= 0.95:
        # Critical Risk: >95% full. High chance of overflow.
        overflow_probability = 0.9
        # Recommend a 25% capacity increase
        recommended_capacity = int(round(request.current_capacity * 1.25))
    elif registration_ratio >= 0.80:
        # Warning Risk: 80-95% full. Medium chance of overflow.
        overflow_probability = 0.6
        # Recommend a 15% capacity increase
        recommended_capacity = int(round(request.current_capacity * 1.15))
    else:
        # Normal Risk: <80% full. Low chance of overflow.
        overflow_probability = 0.1
        # No change needed
        recommended_capacity = request.current_capacity

    return CapacityManagementResponse(
        recommended_capacity=recommended_capacity,
        overflow_probability=overflow_probability,
    )


def optimize_resources(
    request: ResourceAllocationRequest,
) -> ResourceAllocationResponse:
    """
    Assigns staff to sessions using a greedy algorithm that prioritizes
    critical sessions first.
    """
    # Define the sort order for priorities
    priority_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    # Sort sessions by priority to handle the most important ones first
    sorted_sessions = sorted(
        request.sessions, key=lambda s: priority_map.get(s.priority, 4)
    )

    available_staff_ids = {s.staff_id for s in request.staff}
    staff_skills_map = {s.staff_id: set(s.skills) for s in request.staff}

    assignments = []
    unstaffed = []

    for session in sorted_sessions:
        assigned_staff_id = None
        # Find a suitable, available staff member
        for staff_id in available_staff_ids:
            # Check if the staff has the required skill (if any)
            has_required_skill = (
                not session.required_skill
                or session.required_skill in staff_skills_map.get(staff_id, set())
            )

            if has_required_skill:
                assigned_staff_id = staff_id
                break  # Found a suitable staff member

        if assigned_staff_id:
            assignments.append(
                ResourceAllocationResponse.StaffAssignment(
                    staff_id=assigned_staff_id, assigned_session_id=session.session_id
                )
            )
            # This staff member is now booked
            available_staff_ids.remove(assigned_staff_id)
        else:
            unstaffed.append(
                ResourceAllocationResponse.UnstaffedSession(
                    session_id=session.session_id,
                    reason="No available staff with the required skills.",
                )
            )

    efficiency = len(assignments) / len(request.sessions) if request.sessions else 1.0

    return ResourceAllocationResponse(
        staff_assignments=assignments,
        unstaffed_sessions=unstaffed,
        overall_efficiency=round(efficiency, 2),
    )

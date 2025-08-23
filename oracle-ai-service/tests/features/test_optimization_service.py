# tests/features/test_optimization_service.py

import pytest
from app.features.optimization.service import *
from app.features.optimization.schemas import *


def test_optimize_schedule_finds_and_solves_overcrowding(mocker):
    """
    Tests that the solver identifies a session with predicted attendance
    exceeding room capacity and suggests a move to a suitable larger room.
    """
    # 1. Arrange
    # A schedule with one clear conflict: ses_2 predicts 120 attendees in a room for 100.
    current_schedule = [
        ScheduleOptimizationRequest.SessionInput(
            session_id="ses_1",
            start_time="2025-10-26T10:00:00Z",
            end_time="2025-10-26T11:00:00Z",
            predicted_attendance=50,
            room_id="room_A",
            room_capacity=75,
        ),
        ScheduleOptimizationRequest.SessionInput(
            session_id="ses_2",
            start_time="2025-10-26T10:00:00Z",
            end_time="2025-10-26T11:00:00Z",
            predicted_attendance=120,
            room_id="room_B",
            room_capacity=100,
        ),
    ]
    request = ScheduleOptimizationRequest(
        event_id="evt_123", current_schedule=current_schedule
    )

    # Mock the DB call to fetch available rooms.
    # The "best" new room for ses_2 is room_C (capacity 150), as room_D is too big.
    available_rooms = [
        {"id": "room_A", "capacity": 75},
        {"id": "room_B", "capacity": 100},
        {"id": "room_C", "capacity": 150},
        {"id": "room_D", "capacity": 500},
    ]
    mocker.patch(
        "app.features.optimization.service._get_available_rooms_from_db",
        return_value=available_rooms,
    )

    # 2. Act
    response = optimize_schedule(request)

    # 3. Assert
    assert (
        len(response.optimized_schedule) == 1
    )  # It should find exactly one problem to solve.

    change = response.optimized_schedule[0]
    assert change.session_id == "ses_2"
    assert "Predicted attendance (120) exceeds room capacity (100)" in change.reason
    assert change.recommended_room_id == "room_C"  # It found the best-fit larger room.


def test_optimize_schedule_with_no_conflicts():
    """
    Tests the "happy path" where the schedule is already optimal
    and no changes are needed.
    """
    # 1. Arrange
    # A perfectly fine schedule with no conflicts.
    current_schedule = [
        ScheduleOptimizationRequest.SessionInput(
            session_id="ses_1",
            start_time="2025-10-26T10:00:00Z",
            end_time="2025-10-26T11:00:00Z",
            predicted_attendance=50,
            room_id="room_A",
            room_capacity=75,
        ),
    ]
    request = ScheduleOptimizationRequest(
        event_id="evt_123", current_schedule=current_schedule
    )

    # 2. Act
    response = optimize_schedule(request)

    # 3. Assert
    # The list of changes should be empty.
    assert len(response.optimized_schedule) == 0


@pytest.mark.parametrize(
    "current_regs, current_cap, expected_overflow_prob, expected_new_cap",
    [
        # Test Case 1: Critical Risk (98% full)
        (98, 100, 0.9, 125),  # Expect ~90% overflow prob, recommend 25% increase
        # Test Case 2: Warning Risk (85% full)
        (170, 200, 0.6, 230),  # Expect ~60% overflow prob, recommend 15% increase
        # Test Case 3: Normal (50% full)
        (50, 100, 0.1, 100),  # Expect low overflow prob, recommend no change
    ],
)
def test_manage_capacity(
    current_regs, current_cap, expected_overflow_prob, expected_new_cap
):
    """
    Tests that the capacity management service correctly assesses risk
    and recommends appropriate capacity changes based on registration velocity.
    """
    # 1. Arrange
    request = CapacityManagementRequest(
        session_id="ses_1",
        current_capacity=current_cap,
        current_registrations=current_regs,
    )

    # 2. Act
    response = manage_capacity(request)

    # 3. Assert
    assert response.recommended_capacity == expected_new_cap
    assert response.overflow_probability == pytest.approx(
        expected_overflow_prob, abs=0.05
    )


def test_optimize_resources_prioritizes_critical_sessions():
    """
    Tests that the resource allocator correctly assigns a skilled staff member
    to a critical session first, even if other sessions are listed before it.
    """
    # 1. Arrange
    sessions_to_staff = [
        ResourceAllocationRequest.SessionRequirement(
            session_id="ses_low", priority="low"
        ),
        ResourceAllocationRequest.SessionRequirement(
            session_id="ses_critical", priority="critical", required_skill="AV_Tech"
        ),
    ]
    available_staff = [
        ResourceAllocationRequest.StaffMember(
            staff_id="staff_A", skills=["AV_Tech", "Support"]
        ),
        ResourceAllocationRequest.StaffMember(staff_id="staff_B", skills=["Support"]),
    ]
    request = ResourceAllocationRequest(
        event_id="evt_123", sessions=sessions_to_staff, staff=available_staff
    )

    # 2. Act
    response = optimize_resources(request)

    # 3. Assert
    assert len(response.staff_assignments) == 2
    assert len(response.unstaffed_sessions) == 0

    assignments = {
        a.assigned_session_id: a.staff_id for a in response.staff_assignments
    }

    # Critical session should be assigned the only AV Tech
    assert assignments["ses_critical"] == "staff_A"

    # The low priority session gets the remaining staff member
    assert assignments["ses_low"] == "staff_B"

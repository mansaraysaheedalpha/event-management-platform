# app/api/v1/endpoints/ab_testing.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.crud_ab_test import ab_test, ab_test_event
from app.crud.crud_event import event as event_crud
from app.schemas.ab_test import (
    ABTestCreate,
    ABTestUpdate,
    ABTestResponse,
    ABTestEventCreate,
    BatchABTestEventCreate,
    ABTestResults,
    ABTestListItem,
    ABTestVariantStats
)
from app.schemas.token import TokenPayload

router = APIRouter()

# Import limiter for rate limiting
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


# ==================== A/B Test Management ====================

@router.post("/ab-tests", response_model=ABTestResponse, status_code=status.HTTP_201_CREATED)
def create_ab_test(
    *,
    db: Session = Depends(deps.get_db),
    test_in: ABTestCreate,
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Create a new A/B test.

    **Required fields**:
    - test_id: Unique identifier (e.g., "checkout_button_color")
    - name: Human-readable name
    - event_id: Event this test applies to
    - variants: Array of at least 2 variants
    - goal_metric: Primary metric to measure

    **Features**:
    - Test starts inactive (must be manually activated)
    - Variants can have different weights for distribution
    - Optional audience targeting
    - Configurable minimum sample size

    **Errors**:
    - 400: Invalid test configuration
    - 403: Not authorized to create tests for this event
    - 404: Event not found
    - 409: Test with same test_id already exists
    """
    # Verify user owns the event
    db_event = event_crud.get(db, id=test_in.event_id)
    if not db_event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{test_in.event_id}' not found"
        )

    if db_event.owner_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to create A/B tests for this event"
        )

    # Check if test_id already exists
    existing = ab_test.get(db, test_id=test_in.test_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A/B test with test_id '{test_in.test_id}' already exists"
        )

    # Validate variants
    if len(test_in.variants) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A/B test must have at least 2 variants"
        )

    # Validate unique variant IDs
    variant_ids = [v.id for v in test_in.variants]
    if len(variant_ids) != len(set(variant_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Variant IDs must be unique"
        )

    test = ab_test.create(db, obj_in=test_in)
    return test


@router.get("/ab-tests/{test_id}", response_model=ABTestResponse)
def get_ab_test(
    *,
    db: Session = Depends(deps.get_db),
    test_id: str,
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Get A/B test by test_id.

    **Returns**:
    - Complete test configuration
    - Current status (active/inactive)
    - All variant definitions
    """
    test = ab_test.get(db, test_id=test_id)
    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )
    return test


@router.get("/events/{event_id}/ab-tests", response_model=List[ABTestResponse])
def get_event_ab_tests(
    *,
    db: Session = Depends(deps.get_db),
    event_id: str,
    active_only: bool = True
):
    """
    Get all A/B tests for an event.

    **Query Parameters**:
    - active_only: If true, only return active tests (default: true)

    **Use Case**:
    - Frontend fetches active tests on page load
    - Admin views all tests (active + inactive)

    **Public endpoint** - No authentication required
    """
    tests = ab_test.get_by_event(db, event_id=event_id, active_only=active_only)
    return tests


@router.put("/ab-tests/{test_id}", response_model=ABTestResponse)
def update_ab_test(
    *,
    db: Session = Depends(deps.get_db),
    test_id: str,
    test_in: ABTestUpdate,
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Update an A/B test.

    **Updatable fields**:
    - name, description
    - is_active (activates/deactivates test)
    - variants (add/remove/modify)
    - goal_metric
    - target_audience

    **Important**:
    - Activating a test sets started_at timestamp
    - Deactivating a test sets ended_at timestamp
    - Cannot modify variants of an active test (deactivate first)

    **Errors**:
    - 403: Not authorized to update this test
    - 404: Test not found
    - 400: Invalid update (e.g., modifying active test variants)
    """
    db_test = ab_test.get(db, test_id=test_id)
    if not db_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    # Verify user owns the event
    db_event = event_crud.get(db, id=db_test.event_id)
    if db_event and db_event.owner_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update A/B tests for this event"
        )

    # Prevent modifying variants of active test
    if db_test.is_active and test_in.variants is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify variants of an active test. Deactivate the test first."
        )

    updated_test = ab_test.update(db, db_obj=db_test, obj_in=test_in)
    return updated_test


@router.delete("/ab-tests/{test_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ab_test(
    *,
    db: Session = Depends(deps.get_db),
    test_id: str,
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Delete an A/B test (soft delete - deactivates it).

    **Behavior**:
    - Sets is_active = false
    - Sets ended_at timestamp
    - Preserves all historical data

    **Errors**:
    - 403: Not authorized to delete this test
    - 404: Test not found
    """
    # Get test first to check authorization
    db_test = ab_test.get(db, test_id=test_id)
    if not db_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    # Verify user owns the event
    db_event = event_crud.get(db, id=db_test.event_id)
    if db_event and db_event.owner_id != current_user.sub:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete A/B tests for this event"
        )

    # Perform soft delete
    db_test = ab_test.delete(db, test_id=test_id)
    if not db_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )
    return None


# ==================== Event Tracking ====================

@router.post("/ab-tests/track", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("100/minute")  # Rate limit: 100 requests per minute per IP
def track_ab_test_event(
    request: Request,  # Required for rate limiting
    *,
    db: Session = Depends(deps.get_db),
    event_in: BatchABTestEventCreate,
    background_tasks: BackgroundTasks
):
    """
    Track A/B test events (batch endpoint).

    **Event Types**:
    - variant_view: User saw a variant
    - goal_conversion: User completed the goal action
    - secondary_metric: User completed a secondary action

    **Request Body**:
    ```json
    {
      "events": [
        {
          "test_id": "checkout_button_color",
          "event_id": "evt_123",
          "session_token": "sess_abc",
          "variant_id": "green_button",
          "event_type": "variant_view",
          "goal_achieved": false
        },
        {
          "test_id": "checkout_button_color",
          "event_id": "evt_123",
          "session_token": "sess_abc",
          "variant_id": "green_button",
          "event_type": "goal_conversion",
          "goal_achieved": true,
          "goal_value": 4999
        }
      ]
    }
    ```

    **Features**:
    - Batch processing (up to 100 events)
    - Async processing via background tasks
    - Returns immediately (202 Accepted)

    **Public endpoint** - No authentication required
    """
    def process_events():
        # Create new session for background task to avoid "Session is closed" error
        from app.db.session import SessionLocal
        import logging

        logger = logging.getLogger(__name__)
        db_task = SessionLocal()
        try:
            ab_test_event.track_events_batch(db_task, events=event_in.events)
            db_task.commit()
        except Exception as e:
            db_task.rollback()
            logger.error(f"Failed to track A/B test events: {e}")
        finally:
            db_task.close()

    background_tasks.add_task(process_events)

    return {
        "status": "accepted",
        "queued": len(event_in.events)
    }


# ==================== Results & Analytics ====================

@router.get("/ab-tests/{test_id}/results", response_model=ABTestResults)
def get_ab_test_results(
    *,
    db: Session = Depends(deps.get_db),
    test_id: str,
    current_user: TokenPayload = Depends(deps.get_current_user)
):
    """
    Get comprehensive results for an A/B test.

    **Returns**:
    - Impressions and conversions per variant
    - Conversion rates
    - Average goal value per variant
    - Statistical significance (confidence level)
    - Winner recommendation

    **Statistical Analysis**:
    - Uses chi-square test for significance
    - Requires minimum 30 impressions per variant
    - Declares winner at 95% confidence level

    **Response Example**:
    ```json
    {
      "test_id": "checkout_button_color",
      "test_name": "Checkout Button Color Test",
      "is_active": true,
      "total_impressions": 1523,
      "total_conversions": 89,
      "variants": [
        {
          "variant_id": "green_button",
          "variant_name": "Green Button",
          "impressions": 762,
          "conversions": 51,
          "conversion_rate": 6.69,
          "average_value": 49.99,
          "confidence_level": 0.97
        },
        {
          "variant_id": "blue_button",
          "variant_name": "Blue Button",
          "impressions": 761,
          "conversions": 38,
          "conversion_rate": 4.99,
          "average_value": 49.99,
          "confidence_level": 0.97
        }
      ],
      "winner": "green_button",
      "confidence": 0.97,
      "recommendation": "Green button variant is the winner with 97% confidence. Consider making it the default."
    }
    ```

    **Errors**:
    - 404: Test not found
    """
    db_test = ab_test.get(db, test_id=test_id)
    if not db_test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    # Get results
    results = ab_test_event.get_test_results(db, test_id=test_id)

    # Get total impressions
    total_impressions = ab_test_event.get_impressions_count(db, test_id=test_id)

    # Get total conversions
    total_conversions = sum(v["conversions"] for v in results["variant_stats"])

    # Map variant IDs to names
    variant_map = {v["id"]: v["name"] for v in db_test.variants}

    # Build variant stats with names
    variant_stats = [
        ABTestVariantStats(
            variant_id=v["variant_id"],
            variant_name=variant_map.get(v["variant_id"], v["variant_id"]),
            impressions=v["impressions"],
            conversions=v["conversions"],
            conversion_rate=v["conversion_rate"],
            average_value=v["average_value"],
            confidence_level=v["confidence_level"]
        )
        for v in results["variant_stats"]
    ]

    # Generate recommendation
    if results["winner"] and results["confidence"]:
        winner_name = variant_map.get(results["winner"], results["winner"])
        confidence_pct = int(results["confidence"] * 100)
        recommendation = (
            f"{winner_name} variant is the winner with {confidence_pct}% confidence. "
            f"Consider making it the default."
        )
    elif total_impressions < db_test.min_sample_size:
        recommendation = (
            f"Test needs more data. Current: {total_impressions} impressions. "
            f"Minimum required: {db_test.min_sample_size}."
        )
    else:
        recommendation = (
            "Not enough evidence to declare a winner. "
            "Consider running the test longer or checking variant configurations."
        )

    return ABTestResults(
        test_id=db_test.test_id,
        test_name=db_test.name,
        is_active=db_test.is_active,
        total_impressions=total_impressions,
        total_conversions=total_conversions,
        variants=variant_stats,
        winner=results["winner"],
        confidence=results["confidence"],
        recommendation=recommendation,
        started_at=db_test.started_at,
        ended_at=db_test.ended_at
    )

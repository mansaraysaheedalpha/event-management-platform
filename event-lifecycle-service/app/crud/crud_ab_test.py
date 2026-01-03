# app/crud/crud_ab_test.py
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, func
from datetime import datetime
import scipy.stats as stats
import logging

from app.models.ab_test import ABTest, ABTestEvent
from app.schemas.ab_test import ABTestCreate, ABTestUpdate, ABTestEventCreate

logger = logging.getLogger(__name__)


class CRUDABTest:
    """CRUD operations for A/B tests"""

    def create(self, db: Session, *, obj_in: ABTestCreate) -> ABTest:
        """Create a new A/B test"""
        # Convert variants to JSON-serializable format
        variants_dict = [v.dict() for v in obj_in.variants]

        db_obj = ABTest(
            test_id=obj_in.test_id,
            name=obj_in.name,
            description=obj_in.description,
            event_id=obj_in.event_id,
            variants=variants_dict,
            goal_metric=obj_in.goal_metric.value,
            secondary_metrics=obj_in.secondary_metrics,
            target_audience=obj_in.target_audience,
            min_sample_size=obj_in.min_sample_size,
            is_active=False,  # Start inactive
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def get(self, db: Session, *, test_id: str) -> Optional[ABTest]:
        """Get A/B test by test_id"""
        return db.query(ABTest).filter(ABTest.test_id == test_id).first()

    def get_by_event(self, db: Session, *, event_id: str, active_only: bool = True) -> List[ABTest]:
        """Get all A/B tests for an event"""
        query = db.query(ABTest).filter(ABTest.event_id == event_id)
        if active_only:
            query = query.filter(ABTest.is_active == True)
        return query.order_by(ABTest.created_at.desc()).all()

    def get_multi(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[ABTest]:
        """Get multiple A/B tests"""
        return db.query(ABTest).order_by(ABTest.created_at.desc()).offset(skip).limit(limit).all()

    def update(self, db: Session, *, db_obj: ABTest, obj_in: ABTestUpdate) -> ABTest:
        """Update an A/B test"""
        update_data = obj_in.dict(exclude_unset=True)

        # Handle variants conversion
        if 'variants' in update_data and update_data['variants']:
            update_data['variants'] = [v.dict() if hasattr(v, 'dict') else v for v in update_data['variants']]

        # Handle goal_metric enum
        if 'goal_metric' in update_data and update_data['goal_metric']:
            update_data['goal_metric'] = update_data['goal_metric'].value

        # Update started_at/ended_at based on is_active changes
        if 'is_active' in update_data:
            if update_data['is_active'] and not db_obj.is_active:
                # Activating test
                update_data['started_at'] = datetime.utcnow()
            elif not update_data['is_active'] and db_obj.is_active:
                # Deactivating test
                update_data['ended_at'] = datetime.utcnow()

        update_data['updated_at'] = datetime.utcnow()

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, *, test_id: str) -> Optional[ABTest]:
        """Delete an A/B test (soft delete by deactivating)"""
        db_obj = self.get(db, test_id=test_id)
        if db_obj:
            db_obj.is_active = False
            db_obj.ended_at = datetime.utcnow()
            db.add(db_obj)
            db.commit()
        return db_obj


class CRUDABTestEvent:
    """CRUD operations for A/B test events"""

    def track_event(self, db: Session, *, obj_in: ABTestEventCreate) -> ABTestEvent:
        """Track a single A/B test event"""
        db_obj = ABTestEvent(**obj_in.dict())
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def track_events_batch(self, db: Session, *, events: List[ABTestEventCreate]) -> int:
        """Track multiple A/B test events in batch"""
        db_objs = [ABTestEvent(**event.dict()) for event in events]
        db.bulk_save_objects(db_objs)
        db.commit()
        return len(db_objs)

    def get_test_results(self, db: Session, *, test_id: str) -> Dict[str, Any]:
        """Get comprehensive results for an A/B test"""
        # Get variant stats
        variant_stats = db.execute(text("""
            WITH variant_data AS (
                SELECT
                    variant_id,
                    COUNT(*) FILTER (WHERE event_type = 'variant_view') as impressions,
                    COUNT(*) FILTER (WHERE event_type = 'goal_conversion' AND goal_achieved = true) as conversions,
                    AVG(goal_value) FILTER (WHERE event_type = 'goal_conversion' AND goal_achieved = true) as avg_value
                FROM ab_test_events
                WHERE test_id = :test_id
                GROUP BY variant_id
            )
            SELECT
                variant_id,
                impressions,
                conversions,
                COALESCE(avg_value, 0) as avg_value,
                CASE
                    WHEN impressions > 0
                    THEN ROUND((conversions::decimal / impressions) * 100, 2)
                    ELSE 0
                END as conversion_rate
            FROM variant_data
            ORDER BY conversion_rate DESC
        """), {"test_id": test_id}).fetchall()

        # Calculate statistical significance if we have 2 variants
        if len(variant_stats) == 2:
            v1, v2 = variant_stats[0], variant_stats[1]
            confidence = self._calculate_confidence(
                v1[1], v1[2],  # impressions, conversions
                v2[1], v2[2]
            )
        else:
            confidence = None

        return {
            "variant_stats": [
                {
                    "variant_id": row[0],
                    "impressions": row[1],
                    "conversions": row[2],
                    "average_value": float(row[3]) if row[3] else 0.0,
                    "conversion_rate": float(row[4]),
                    "confidence_level": confidence if confidence else 0.0
                }
                for row in variant_stats
            ],
            "winner": variant_stats[0][0] if variant_stats and confidence and confidence >= 0.95 else None,
            "confidence": confidence
        }

    def _calculate_confidence(self, n1: int, x1: int, n2: int, x2: int) -> float:
        """Calculate statistical significance using chi-square test"""
        if n1 < 30 or n2 < 30:
            return 0.0  # Insufficient data

        # Create contingency table
        observed = [[x1, n1 - x1], [x2, n2 - x2]]

        try:
            chi2, p_value, dof, expected = stats.chi2_contingency(observed)
            # Return confidence level (1 - p_value)
            return min(1.0 - p_value, 1.0)
        except (ValueError, RuntimeError) as e:
            logger.warning(f"Statistical calculation failed for chi-square test: {e}")
            return 0.0

    def get_impressions_count(self, db: Session, *, test_id: str) -> int:
        """Get total impressions for a test"""
        result = db.execute(text("""
            SELECT COUNT(*)
            FROM ab_test_events
            WHERE test_id = :test_id AND event_type = 'variant_view'
        """), {"test_id": test_id}).scalar()
        return result or 0


ab_test = CRUDABTest()
ab_test_event = CRUDABTestEvent()

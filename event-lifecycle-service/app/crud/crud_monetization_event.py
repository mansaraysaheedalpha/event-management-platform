# app/crud/crud_monetization_event.py
from typing import List, Optional, Dict, Any
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
import logging

from app.models.monetization_event import MonetizationEvent
from app.schemas.analytics import EventTrackingDTO

logger = logging.getLogger(__name__)


class CRUDMonetizationEvent:
    """CRUD operations for monetization events"""

    def track_event(
        self,
        db: Session,
        *,
        event_data: EventTrackingDTO,
        event_id: str,
        user_id: Optional[str] = None,
        session_token: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> MonetizationEvent:
        """
        Track a single monetization event.
        """
        try:
            event = MonetizationEvent(
                event_id=event_id,
                user_id=user_id,
                session_token=session_token,
                event_type=event_data.event_type,
                entity_type=event_data.entity_type,
                entity_id=event_data.entity_id,
                revenue_cents=event_data.revenue_cents or 0,
                context=event_data.context or {},
                user_agent=user_agent,
                ip_address=ip_address
            )
            db.add(event)
            db.commit()
            db.refresh(event)
            return event
        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            db.rollback()
            raise

    def track_events_batch(
        self,
        db: Session,
        *,
        events: List[EventTrackingDTO],
        event_id: str,
        user_id: Optional[str] = None,
        session_token: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> int:
        """
        Track multiple monetization events in batch.
        Returns the number of events tracked.
        """
        try:
            event_objects = [
                MonetizationEvent(
                    event_id=event_id,
                    user_id=user_id,
                    session_token=session_token,
                    event_type=e.event_type,
                    entity_type=e.entity_type,
                    entity_id=e.entity_id,
                    revenue_cents=e.revenue_cents or 0,
                    context=e.context or {},
                    user_agent=user_agent,
                    ip_address=ip_address
                )
                for e in events
            ]
            db.bulk_save_objects(event_objects)
            db.commit()
            return len(event_objects)
        except Exception as e:
            logger.error(f"Error tracking events batch: {e}")
            db.rollback()
            raise

    def get_event_analytics(
        self,
        db: Session,
        *,
        event_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive monetization analytics for an event.
        """
        # Build date filter
        filters = [MonetizationEvent.event_id == event_id]
        if date_from:
            filters.append(func.date(MonetizationEvent.created_at) >= date_from)
        if date_to:
            filters.append(func.date(MonetizationEvent.created_at) <= date_to)

        # Get offer analytics
        offer_stats = db.query(
            func.count().filter(MonetizationEvent.event_type == 'OFFER_VIEW').label('views'),
            func.count().filter(MonetizationEvent.event_type == 'OFFER_CLICK').label('clicks'),
            func.count().filter(MonetizationEvent.event_type == 'OFFER_ADD_TO_CART').label('add_to_cart'),
            func.count().filter(MonetizationEvent.event_type == 'OFFER_PURCHASE').label('purchases'),
            func.sum(MonetizationEvent.revenue_cents).filter(
                MonetizationEvent.event_type == 'OFFER_PURCHASE'
            ).label('revenue_cents')
        ).filter(
            and_(*filters),
            MonetizationEvent.entity_type == 'OFFER'
        ).first()

        views = offer_stats.views or 0
        clicks = offer_stats.clicks or 0
        add_to_cart = offer_stats.add_to_cart or 0
        purchases = offer_stats.purchases or 0
        revenue_cents = offer_stats.revenue_cents or 0

        # Calculate conversion rates
        view_to_click_rate = round((clicks / views * 100), 2) if views > 0 else 0
        click_to_cart_rate = round((add_to_cart / clicks * 100), 2) if clicks > 0 else 0
        cart_to_purchase_rate = round((purchases / add_to_cart * 100), 2) if add_to_cart > 0 else 0
        overall_conversion_rate = round((purchases / views * 100), 2) if views > 0 else 0

        # Get ad analytics
        ad_stats = db.query(
            func.count().filter(MonetizationEvent.event_type == 'AD_IMPRESSION').label('impressions'),
            func.count().filter(MonetizationEvent.event_type == 'AD_VIEWABLE_IMPRESSION').label('viewable_impressions'),
            func.count().filter(MonetizationEvent.event_type == 'AD_CLICK').label('clicks'),
        ).filter(
            and_(*filters),
            MonetizationEvent.entity_type == 'AD'
        ).first()

        ad_impressions = ad_stats.impressions or 0
        ad_viewable_impressions = ad_stats.viewable_impressions or 0
        ad_clicks = ad_stats.clicks or 0
        ad_ctr = round((ad_clicks / ad_impressions * 100), 2) if ad_impressions > 0 else 0

        # Get waitlist analytics
        waitlist_stats = db.query(
            func.count().filter(MonetizationEvent.event_type == 'WAITLIST_JOIN').label('joins'),
            func.count().filter(MonetizationEvent.event_type == 'WAITLIST_OFFER_SENT').label('offers_sent'),
            func.count().filter(MonetizationEvent.event_type == 'WAITLIST_OFFER_ACCEPTED').label('accepted'),
            func.count().filter(MonetizationEvent.event_type == 'WAITLIST_OFFER_DECLINED').label('declined'),
            func.count().filter(MonetizationEvent.event_type == 'WAITLIST_OFFER_EXPIRED').label('expired'),
        ).filter(
            and_(*filters),
            MonetizationEvent.entity_type == 'WAITLIST'
        ).first()

        joins = waitlist_stats.joins or 0
        offers_sent = waitlist_stats.offers_sent or 0
        accepted = waitlist_stats.accepted or 0
        declined = waitlist_stats.declined or 0
        expired = waitlist_stats.expired or 0
        acceptance_rate = round((accepted / offers_sent * 100), 2) if offers_sent > 0 else 0

        # Get revenue by day
        revenue_by_day = db.query(
            func.date(MonetizationEvent.created_at).label('date'),
            func.sum(MonetizationEvent.revenue_cents).label('amount')
        ).filter(
            and_(*filters),
            MonetizationEvent.event_type == 'OFFER_PURCHASE'
        ).group_by(
            func.date(MonetizationEvent.created_at)
        ).order_by(
            func.date(MonetizationEvent.created_at)
        ).all()

        # Get unique users
        unique_users = db.query(
            func.count(func.distinct(func.coalesce(MonetizationEvent.user_id, MonetizationEvent.session_token)))
        ).filter(and_(*filters)).scalar() or 0

        # Total interactions
        total_interactions = db.query(func.count(MonetizationEvent.id)).filter(and_(*filters)).scalar() or 0

        # Get top performing offers
        top_offers = db.query(
            MonetizationEvent.entity_id,
            func.count().filter(MonetizationEvent.event_type == 'OFFER_VIEW').label('views'),
            func.count().filter(MonetizationEvent.event_type == 'OFFER_PURCHASE').label('purchases'),
            func.sum(MonetizationEvent.revenue_cents).filter(
                MonetizationEvent.event_type == 'OFFER_PURCHASE'
            ).label('revenue')
        ).filter(
            and_(*filters),
            MonetizationEvent.entity_type == 'OFFER'
        ).group_by(
            MonetizationEvent.entity_id
        ).order_by(
            func.sum(MonetizationEvent.revenue_cents).desc()
        ).limit(5).all()

        return {
            "revenue": {
                "total_cents": revenue_cents,
                "from_offers": revenue_cents,
                "from_ads": 0,
                "by_day": [{"date": str(r.date), "amount": r.amount} for r in revenue_by_day]
            },
            "offers": {
                "total_views": views,
                "total_clicks": clicks,
                "total_add_to_cart": add_to_cart,
                "total_purchases": purchases,
                "conversion_rate": overall_conversion_rate,
                "view_to_click_rate": view_to_click_rate,
                "click_to_cart_rate": click_to_cart_rate,
                "cart_to_purchase_rate": cart_to_purchase_rate,
                "top_performers": [
                    {
                        "offer_id": o.entity_id,
                        "views": o.views,
                        "purchases": o.purchases,
                        "revenue_cents": o.revenue or 0,
                        "conversion_rate": round((o.purchases / o.views * 100), 2) if o.views > 0 else 0
                    }
                    for o in top_offers
                ]
            },
            "ads": {
                "total_impressions": ad_impressions,
                "viewable_impressions": ad_viewable_impressions,
                "total_clicks": ad_clicks,
                "average_ctr": ad_ctr,
                "by_placement": {}  # Can be enhanced later
            },
            "waitlist": {
                "total_joins": joins,
                "offers_sent": offers_sent,
                "offers_accepted": accepted,
                "offers_declined": declined,
                "offers_expired": expired,
                "acceptance_rate": acceptance_rate
            },
            "total_interactions": total_interactions,
            "unique_users": unique_users
        }

    def get_conversion_funnels(
        self,
        db: Session,
        *,
        event_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversion funnels from materialized view.
        """
        query = text("""
            SELECT
                mcf.*,
                o.title as offer_name
            FROM monetization_conversion_funnels mcf
            LEFT JOIN offers o ON o.id = mcf.offer_id
            WHERE o.event_id = :event_id
            ORDER BY mcf.revenue_cents DESC
        """)

        result = db.execute(query, {"event_id": event_id}).fetchall()

        return [
            {
                "offer_id": str(r.offer_id),
                "offer_name": r.offer_name,
                "views": r.views,
                "clicks": r.clicks,
                "add_to_cart": r.add_to_cart,
                "purchases": r.purchases,
                "revenue_cents": r.revenue_cents,
                "view_to_click_rate": float(r.view_to_click_rate or 0),
                "click_to_cart_rate": float(r.click_to_cart_rate or 0),
                "cart_to_purchase_rate": float(r.cart_to_purchase_rate or 0),
                "overall_conversion_rate": float(r.overall_conversion_rate or 0)
            }
            for r in result
        ]

    def refresh_materialized_views(self, db: Session) -> None:
        """
        Refresh all monetization materialized views.
        Should be called periodically (e.g., hourly via cron).
        """
        try:
            # Refresh conversion funnels view
            db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY monetization_conversion_funnels"))
            db.commit()
            logger.info("Successfully refreshed monetization_conversion_funnels")
        except Exception as e:
            logger.error(f"Error refreshing materialized views: {e}")
            db.rollback()
            raise


monetization_event = CRUDMonetizationEvent()

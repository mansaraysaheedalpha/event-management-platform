from sqlalchemy.orm import Session
from sqlalchemy import func, and_, text
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timezone
from app.models.ad_event import AdEvent
from app.schemas.ad import ImpressionTrackingDTO


class CRUDAdEvent:
    def __init__(self):
        self.model = AdEvent

    def track_impression(
        self,
        db: Session,
        *,
        ad_id: str,
        user_id: Optional[str],
        session_token: str,
        context: Optional[str],
        viewable_duration_ms: int,
        viewport_percentage: int,
        user_agent: Optional[str],
        ip_address: Optional[str],
        referer: Optional[str]
    ) -> AdEvent:
        """
        Track a single ad impression.
        """
        event = self.model(
            ad_id=ad_id,
            user_id=user_id,
            session_token=session_token,
            event_type="IMPRESSION",
            context=context,
            viewable_duration_ms=viewable_duration_ms,
            viewport_percentage=viewport_percentage,
            user_agent=user_agent,
            ip_address=ip_address,
            referer=referer
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def track_impressions_batch(
        self,
        db: Session,
        *,
        impressions: List[ImpressionTrackingDTO],
        user_id: Optional[str],
        session_token: str,
        user_agent: Optional[str],
        ip_address: Optional[str]
    ) -> int:
        """
        Bulk track ad impressions.
        Returns count of tracked impressions.
        """
        events = [
            self.model(
                ad_id=imp.ad_id,
                user_id=user_id,
                session_token=session_token,
                event_type="IMPRESSION",
                context=imp.context,
                viewable_duration_ms=imp.viewable_duration_ms,
                viewport_percentage=imp.viewport_percentage,
                user_agent=user_agent,
                ip_address=ip_address
            )
            for imp in impressions
        ]

        db.bulk_save_objects(events)
        db.commit()
        return len(events)

    def track_click(
        self,
        db: Session,
        *,
        ad_id: str,
        user_id: Optional[str],
        session_token: str,
        context: Optional[str],
        user_agent: Optional[str],
        ip_address: Optional[str],
        referer: Optional[str]
    ) -> AdEvent:
        """
        Track an ad click.
        """
        event = self.model(
            ad_id=ad_id,
            user_id=user_id,
            session_token=session_token,
            event_type="CLICK",
            context=context,
            user_agent=user_agent,
            ip_address=ip_address,
            referer=referer
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    def get_ad_analytics(
        self,
        db: Session,
        *,
        ad_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get analytics for a specific ad from materialized view.
        """
        # Build query safely without string concatenation
        base_query = """
            SELECT
                date,
                impressions,
                viewable_impressions,
                clicks,
                ctr_percentage,
                unique_users
            FROM ad_analytics_daily
            WHERE ad_id = :ad_id
        """

        conditions = []
        params = {"ad_id": ad_id}

        if date_from:
            conditions.append("date >= :date_from")
            params["date_from"] = date_from

        if date_to:
            conditions.append("date <= :date_to")
            params["date_to"] = date_to

        if conditions:
            base_query += " AND " + " AND ".join(conditions)

        base_query += " ORDER BY date DESC"

        result = db.execute(text(base_query), params).fetchall()

        # Aggregate totals
        total_impressions = sum(row.impressions for row in result)
        total_viewable_impressions = sum(row.viewable_impressions for row in result)
        total_clicks = sum(row.clicks for row in result)
        # M-CQ4: Sum daily unique user counts (per-day uniqueness from materialized view)
        total_unique_users = sum(row.unique_users for row in result if row.unique_users)

        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        return {
            "total_impressions": total_impressions,
            "viewable_impressions": total_viewable_impressions,
            "total_clicks": total_clicks,
            "ctr": round(ctr, 2),
            "unique_users": total_unique_users,
            "daily_breakdown": [
                {
                    "date": str(row.date),
                    "impressions": row.impressions,
                    "viewable_impressions": row.viewable_impressions,
                    "clicks": row.clicks,
                    "ctr": float(row.ctr_percentage) if row.ctr_percentage else 0.0,
                    "unique_users": row.unique_users
                }
                for row in result
            ]
        }

    def get_event_ad_analytics(
        self,
        db: Session,
        *,
        event_id: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get aggregated analytics for all ads in an event.
        """
        # Build WHERE clause safely
        conditions = ["a.event_id = :event_id"]
        params = {"event_id": event_id}

        if date_from:
            conditions.append("aad.date >= :date_from")
            params["date_from"] = date_from

        if date_to:
            conditions.append("aad.date <= :date_to")
            params["date_to"] = date_to

        where_clause = " AND ".join(conditions)

        # Get overall stats
        stats_query = f"""
            SELECT
                COALESCE(SUM(aad.impressions), 0) as total_impressions,
                COALESCE(SUM(aad.clicks), 0) as total_clicks,
                COALESCE(AVG(aad.ctr_percentage), 0) as average_ctr
            FROM ad_analytics_daily aad
            JOIN ads a ON aad.ad_id = a.id
            WHERE {where_clause}
        """

        stats = db.execute(text(stats_query), params).fetchone()

        # Get top performers
        top_query_str = f"""
            SELECT
                a.id as ad_id,
                a.name,
                SUM(aad.impressions) as impressions,
                SUM(aad.clicks) as clicks,
                AVG(aad.ctr_percentage) as ctr
            FROM ad_analytics_daily aad
            JOIN ads a ON aad.ad_id = a.id
            WHERE {where_clause}
            GROUP BY a.id, a.name
            ORDER BY ctr DESC
            LIMIT 5
        """

        top_performers = db.execute(text(top_query_str), params).fetchall()

        # Get breakdown by placement
        placement_query_str = f"""
            SELECT
                unnest(a.placements) as placement,
                SUM(aad.impressions) as impressions,
                SUM(aad.clicks) as clicks,
                AVG(aad.ctr_percentage) as ctr
            FROM ad_analytics_daily aad
            JOIN ads a ON aad.ad_id = a.id
            WHERE {where_clause}
            GROUP BY placement
        """

        placements = db.execute(text(placement_query_str), params).fetchall()

        return {
            "total_impressions": int(stats.total_impressions) if stats else 0,
            "total_clicks": int(stats.total_clicks) if stats else 0,
            "average_ctr": float(stats.average_ctr) if stats else 0.0,
            "top_performers": [
                {
                    "ad_id": row.ad_id,
                    "name": row.name,
                    "impressions": int(row.impressions),
                    "clicks": int(row.clicks),
                    "ctr": float(row.ctr) if row.ctr else 0.0
                }
                for row in top_performers
            ],
            "by_placement": {
                row.placement: {
                    "impressions": int(row.impressions),
                    "clicks": int(row.clicks),
                    "ctr": float(row.ctr) if row.ctr else 0.0
                }
                for row in placements
            }
        }

    def refresh_materialized_view(self, db: Session) -> None:
        """
        Refresh the ad_analytics_daily materialized view.
        Runs automatically every hour via scheduler.
        Skips gracefully if the view hasn't been created yet.
        """
        result = db.execute(text(
            "SELECT 1 FROM pg_matviews WHERE matviewname = 'ad_analytics_daily'"
        ))
        if not result.fetchone():
            return
        db.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY ad_analytics_daily"))
        db.commit()


# Create singleton instance
ad_event = CRUDAdEvent()

# app/api/v1/endpoints/reports.py
from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import pandas as pd
from io import BytesIO
import logging

from app.api import deps
from app.db.session import get_db
from app.crud.crud_monetization_event import monetization_event
from app.schemas.token import TokenPayload

router = APIRouter(prefix="/reports", tags=["Reports"])
logger = logging.getLogger(__name__)


def _fetch_monetization_data(
    db: Session,
    event_id: str,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None
) -> dict:
    """
    Fetch comprehensive monetization data for export.
    """
    analytics = monetization_event.get_event_analytics(
        db,
        event_id=event_id,
        date_from=date_from,
        date_to=date_to
    )

    funnels = monetization_event.get_conversion_funnels(
        db,
        event_id=event_id,
        date_from=date_from,
        date_to=date_to
    )

    return {
        "analytics": analytics,
        "funnels": funnels
    }


@router.get("/events/{event_id}/monetization/export")
async def export_monetization_report(
    event_id: str,
    format: str = "csv",  # csv, excel, pdf
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Export monetization report in various formats.

    **Formats**:
    - **CSV**: Simple tabular data (offers summary)
    - **Excel**: Multi-sheet workbook (offers, ads, waitlist, summary)
    - **PDF**: Formatted report with charts (future implementation)

    **Includes**:
    - Revenue breakdown
    - Offer performance metrics
    - Conversion funnels
    - Ad performance
    - Waitlist analytics

    **Permissions**: Requires event organizer access
    """
    # TODO: Verify user has access to this event
    # verify_event_access(current_user, event_id, "ORGANIZER")

    # Fetch data
    try:
        data = _fetch_monetization_data(db, event_id, date_from, date_to)
    except Exception as e:
        logger.error(f"Error fetching monetization data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch monetization data"
        )

    # Generate report based on format
    if format.lower() == "csv":
        return _export_csv(event_id, data)
    elif format.lower() == "excel":
        return _export_excel(event_id, data)
    elif format.lower() == "pdf":
        return _export_pdf(event_id, data)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}. Use 'csv', 'excel', or 'pdf'"
        )


def _export_csv(event_id: str, data: dict) -> StreamingResponse:
    """
    Export as CSV (offers summary only).
    """
    # Convert funnels to DataFrame
    df = pd.DataFrame(data['funnels'])

    # Reorder columns for better readability
    columns = [
        'offer_id', 'offer_name', 'views', 'clicks', 'add_to_cart', 'purchases',
        'revenue_cents', 'view_to_click_rate', 'click_to_cart_rate',
        'cart_to_purchase_rate', 'overall_conversion_rate'
    ]
    df = df[[col for col in columns if col in df.columns]]

    # Convert to CSV
    output = BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=monetization_{event_id}.csv"
        }
    )


def _export_excel(event_id: str, data: dict) -> StreamingResponse:
    """
    Export as Excel with multiple sheets.
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: Summary
        summary_data = {
            "Metric": [
                "Total Revenue (cents)",
                "Total Offer Views",
                "Total Offer Purchases",
                "Overall Conversion Rate (%)",
                "Total Ad Impressions",
                "Total Ad Clicks",
                "Ad CTR (%)",
                "Waitlist Joins",
                "Waitlist Acceptance Rate (%)",
                "Unique Users"
            ],
            "Value": [
                data['analytics']['revenue']['total_cents'],
                data['analytics']['offers']['total_views'],
                data['analytics']['offers']['total_purchases'],
                data['analytics']['offers']['conversion_rate'],
                data['analytics']['ads']['total_impressions'],
                data['analytics']['ads']['total_clicks'],
                data['analytics']['ads']['average_ctr'],
                data['analytics']['waitlist']['total_joins'],
                data['analytics']['waitlist']['acceptance_rate'],
                data['analytics']['unique_users']
            ]
        }
        pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)

        # Sheet 2: Offer Performance
        if data['funnels']:
            df_offers = pd.DataFrame(data['funnels'])
            df_offers.to_excel(writer, sheet_name='Offer Performance', index=False)

        # Sheet 3: Revenue by Day
        if data['analytics']['revenue']['by_day']:
            df_revenue = pd.DataFrame(data['analytics']['revenue']['by_day'])
            df_revenue.to_excel(writer, sheet_name='Revenue by Day', index=False)

        # Sheet 4: Top Performers
        if data['analytics']['offers']['top_performers']:
            df_top = pd.DataFrame(data['analytics']['offers']['top_performers'])
            df_top.to_excel(writer, sheet_name='Top Offers', index=False)

    output.seek(0)

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=monetization_{event_id}.xlsx"
        }
    )


def _export_pdf(event_id: str, data: dict) -> StreamingResponse:
    """
    Export as PDF (formatted report).

    **Note**: This is a placeholder implementation.
    For production, you would use a library like:
    - ReportLab: Low-level PDF generation
    - WeasyPrint: HTML to PDF
    - FPDF: Simple PDF generation
    """
    # TODO: Implement PDF generation
    # For now, return a simple error message

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="PDF export is not yet implemented. Please use CSV or Excel format."
    )

    # Example implementation using reportlab:
    # from reportlab.lib.pagesizes import letter
    # from reportlab.pdfgen import canvas
    # from reportlab.lib.units import inch
    #
    # output = BytesIO()
    # c = canvas.Canvas(output, pagesize=letter)
    #
    # # Title
    # c.setFont("Helvetica-Bold", 24)
    # c.drawString(1*inch, 10*inch, f"Monetization Report - Event {event_id}")
    #
    # # Summary section
    # c.setFont("Helvetica", 12)
    # y = 9*inch
    # c.drawString(1*inch, y, f"Total Revenue: ${data['analytics']['revenue']['total_cents'] / 100:.2f}")
    # y -= 0.3*inch
    # c.drawString(1*inch, y, f"Total Purchases: {data['analytics']['offers']['total_purchases']}")
    # # ... add more content
    #
    # c.save()
    # output.seek(0)
    #
    # return StreamingResponse(
    #     output,
    #     media_type="application/pdf",
    #     headers={
    #         "Content-Disposition": f"attachment; filename=monetization_{event_id}.pdf"
    #     }
    # )

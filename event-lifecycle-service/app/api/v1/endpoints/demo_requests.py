# app/api/v1/endpoints/demo_requests.py
import logging
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.db.session import get_db
from app.crud.crud_demo_request import demo_request as crud_demo_request
from app.schemas.demo_request import DemoRequestCreate, DemoRequestResponse
from app.core.email import (
    send_demo_request_notification,
    send_demo_request_confirmation,
)

router = APIRouter(tags=["Demo Requests"])
logger = logging.getLogger(__name__)


@router.post(
    "/demo-requests",
    response_model=DemoRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("5/minute")
def create_demo_request(
    demo_in: DemoRequestCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Submit a demo request (public endpoint, no auth required).

    Rate limited to 5 requests per minute per IP.
    """
    # Create DB record
    db_obj = crud_demo_request.create(db=db, obj_in=demo_in)

    # Send notification email to team (fire-and-forget)
    try:
        send_demo_request_notification(
            requester_name=f"{demo_in.first_name} {demo_in.last_name}",
            requester_email=demo_in.email,
            company=demo_in.company,
            job_title=demo_in.job_title,
            company_size=demo_in.company_size,
            solution_interest=demo_in.solution_interest,
            preferred_date=demo_in.preferred_date,
            preferred_time=demo_in.preferred_time,
            message=demo_in.message,
        )
    except Exception as e:
        logger.error(f"Failed to send demo notification email: {e}")

    # Send confirmation email to requester (fire-and-forget)
    try:
        send_demo_request_confirmation(
            to_email=demo_in.email,
            requester_name=demo_in.first_name,
            solution_interest=demo_in.solution_interest,
        )
    except Exception as e:
        logger.error(f"Failed to send demo confirmation email: {e}")

    logger.info(f"Demo request created: {db_obj.id} from {demo_in.email}")

    return db_obj

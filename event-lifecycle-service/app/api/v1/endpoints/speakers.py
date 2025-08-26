# /app/api/v1/endpoints/speakers.py
from typing import List, Any
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from datetime import datetime

from app.api import deps
from app.db.session import get_db
from app.crud import crud_speaker
from app.schemas.speaker import Speaker, SpeakerCreate, SpeakerUpdate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Speakers"])


@router.post(
    "/organizations/{orgId}/speakers",
    response_model=Speaker,
    status_code=status.HTTP_201_CREATED,
)
def create_speaker(
    orgId: str,
    speaker_in: SpeakerCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new speaker for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_speaker.speaker.create_with_organization(
        db, obj_in=speaker_in, org_id=orgId
    )


@router.get("/organizations/{orgId}/speakers", response_model=List[Speaker])
def list_speakers(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all speakers for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_speaker.speaker.get_multi_by_organization(db, org_id=orgId)


@router.get("/organizations/{orgId}/speakers/{speakerId}", response_model=Speaker)
def get_speaker(
    orgId: str,
    speakerId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get a specific speaker by ID.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    speaker = crud_speaker.speaker.get(db, id=speakerId)
    if not speaker or speaker.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )
    return speaker


@router.patch("/organizations/{orgId}/speakers/{speakerId}", response_model=Speaker)
def update_speaker(
    orgId: str,
    speakerId: str,
    speaker_in: SpeakerUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update a speaker.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    speaker = crud_speaker.speaker.get(db, id=speakerId)
    if not speaker or speaker.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )

    return crud_speaker.speaker.update(db, db_obj=speaker, obj_in=speaker_in)


@router.delete(
    "/organizations/{orgId}/speakers/{speakerId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_speaker(
    orgId: str,
    speakerId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Soft-delete a speaker by archiving them.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    speaker = crud_speaker.speaker.get(db, id=speakerId)
    if not speaker or speaker.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Speaker not found"
        )

    crud_speaker.speaker.archive(db, id=speakerId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ADD THIS NEW ENDPOINT
@router.get(
    "/organizations/{orgId}/speakers/availability", response_model=List[Speaker]
)
def find_available_speakers(
    orgId: str,
    available_from: datetime,
    available_to: datetime,
    expertise: str | None = None,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Queries for speakers based on expertise and availability.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    available_speakers = crud_speaker.speaker.get_available(
        db,
        org_id=orgId,
        start_time=available_from,
        end_time=available_to,
        expertise=expertise,
    )
    return available_speakers

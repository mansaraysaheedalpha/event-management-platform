# app/api/v1/endpoints/blueprints.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.crud import crud_blueprint, crud_event
from app.schemas.blueprint import (
    EventBlueprint,
    BlueprintCreate,
    BlueprintUpdate,
    InstantiateBlueprintRequest,
)
from app.schemas.event import Event as EventSchema, EventCreate
from app.schemas.token import TokenPayload

router = APIRouter(tags=["Event Blueprints"])


@router.post(
    "/organizations/{orgId}/blueprints",
    response_model=EventBlueprint,
    status_code=status.HTTP_201_CREATED,
)
def create_blueprint(
    orgId: str,
    blueprint_in: BlueprintCreate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Create a new reusable event blueprint.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_blueprint.blueprint.create_with_organization(
        db, obj_in=blueprint_in, org_id=orgId
    )


@router.get("/organizations/{orgId}/blueprints", response_model=List[EventBlueprint])
def list_blueprints(
    orgId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    List all available event blueprints for an organization.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )
    return crud_blueprint.blueprint.get_multi_by_organization(db, org_id=orgId)


@router.get(
    "/organizations/{orgId}/blueprints/{blueprintId}", response_model=EventBlueprint
)
def get_blueprint(
    orgId: str,
    blueprintId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Get a specific event blueprint by ID.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    blueprint = crud_blueprint.blueprint.get(db, id=blueprintId)
    if not blueprint or blueprint.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found"
        )
    return blueprint


@router.patch(
    "/organizations/{orgId}/blueprints/{blueprintId}", response_model=EventBlueprint
)
def update_blueprint(
    orgId: str,
    blueprintId: str,
    blueprint_in: BlueprintUpdate,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Update an event blueprint.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    blueprint = crud_blueprint.blueprint.get(db, id=blueprintId)
    if not blueprint or blueprint.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found"
        )

    return crud_blueprint.blueprint.update(db, db_obj=blueprint, obj_in=blueprint_in)


@router.delete(
    "/organizations/{orgId}/blueprints/{blueprintId}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_blueprint(
    orgId: str,
    blueprintId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Soft-delete an event blueprint by archiving it.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    blueprint = crud_blueprint.blueprint.get(db, id=blueprintId)
    if not blueprint or blueprint.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found"
        )

    crud_blueprint.blueprint.archive(db, id=blueprintId)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/organizations/{orgId}/blueprints/{blueprintId}/instantiate",
    response_model=EventSchema,
    status_code=status.HTTP_201_CREATED,
)
def instantiate_blueprint(
    orgId: str,
    blueprintId: str,
    instantiate_in: InstantiateBlueprintRequest,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
):
    """
    Creates a new, fully configured event from a saved blueprint.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    blueprint = crud_blueprint.blueprint.get(db, id=blueprintId)
    if not blueprint or blueprint.organization_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blueprint not found"
        )

    event_data = {
        **blueprint.template,
        "name": instantiate_in.name,
        "start_date": instantiate_in.start_date,
        "end_date": instantiate_in.end_date,
    }

    event_in = EventCreate(**event_data)
    return crud_event.event.create_with_organization(db, obj_in=event_in, org_id=orgId)

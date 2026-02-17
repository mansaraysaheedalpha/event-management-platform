# app/graphql/venue_mutations.py
"""GraphQL venue sourcing mutations."""
from typing import Optional, List
from strawberry.types import Info
from fastapi import HTTPException

from .. import crud
from ..crud.crud_venue import venue as crud_venue_obj
from ..crud.crud_venue_space import venue_space as crud_space
from ..crud.crud_venue_photo import venue_photo as crud_photo
from ..crud.crud_amenity import amenity as crud_amenity_obj
from ..schemas.venue import VenueCreate, VenueUpdate
from .venue_types import (
    VenueFullType,
    VenueSpaceType,
    VenueSpacePricingType,
    VenuePhotoType,
    VenueAmenityType,
    VenueCreateInputGQL,
    VenueUpdateInputGQL,
    VenueSpaceCreateInputGQL,
    VenueSpaceUpdateInputGQL,
    SpacePricingInputGQL,
    VenueAmenityInputGQL,
    PhotoCategoryEnum,
)
from .venue_queries import _venue_model_to_gql


def _get_user_org(info: Info) -> tuple:
    """Get user and org_id from context or raise."""
    user = info.context.user
    if not user or not user.get("orgId"):
        raise HTTPException(status_code=403, detail="Not authorized")
    return user, user["orgId"]


def _require_admin(info: Info):
    """Verify admin role."""
    user = info.context.user
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    role = user.get("role", "")
    if role.lower() not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")


def create_venue_mutation(venueIn: VenueCreateInputGQL, info: Info) -> VenueFullType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue_data = {
        "name": venueIn.name,
        "description": venueIn.description,
        "address": venueIn.address,
        "city": venueIn.city,
        "country": venueIn.country,
        "latitude": venueIn.latitude,
        "longitude": venueIn.longitude,
        "website": venueIn.website,
        "phone": venueIn.phone,
        "email": venueIn.email,
        "whatsapp": venueIn.whatsapp,
        "is_public": venueIn.isPublic if venueIn.isPublic is not None else True,
    }
    venue_schema = VenueCreate(**venue_data)
    venue = crud_venue_obj.create_with_organization(db, obj_in=venue_schema, org_id=org_id)
    return _venue_model_to_gql(venue)


def update_venue_mutation(id: str, venueIn: VenueUpdateInputGQL, info: Info) -> VenueFullType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")

    update_data = {}
    for field in ("name", "description", "address", "city", "country",
                   "latitude", "longitude", "website", "phone", "email", "whatsapp"):
        val = getattr(venueIn, field)
        if val is not None:
            update_data[field] = val
    if venueIn.isPublic is not None:
        update_data["is_public"] = venueIn.isPublic

    update_schema = VenueUpdate(**update_data)
    updated = crud_venue_obj.update(db, db_obj=venue, obj_in=update_schema)
    return _venue_model_to_gql(updated)


def archive_venue_mutation(id: str, info: Info) -> VenueFullType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")
    archived = crud_venue_obj.archive(db, id=id)
    return _venue_model_to_gql(archived)


def submit_venue_for_review_mutation(id: str, info: Info) -> VenueFullType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")
    if venue.status not in ("draft", "rejected"):
        raise HTTPException(
            status_code=422,
            detail=f"Cannot submit venue with status '{venue.status}'",
        )
    updated = crud_venue_obj.submit_for_review(db, venue_id=id)
    return _venue_model_to_gql(updated)


# --- Spaces ---

def create_venue_space_mutation(spaceIn: VenueSpaceCreateInputGQL, info: Info) -> VenueSpaceType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=spaceIn.venueId)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")

    obj_in = {
        "name": spaceIn.name,
        "description": spaceIn.description,
        "capacity": spaceIn.capacity,
        "floor_level": spaceIn.floorLevel,
        "layout_options": spaceIn.layoutOptions or [],
        "sort_order": spaceIn.sortOrder or 0,
    }
    space = crud_space.create(db, venue_id=spaceIn.venueId, obj_in=obj_in)
    return VenueSpaceType(
        id=space.id,
        venueId=space.venue_id,
        name=space.name,
        description=space.description,
        capacity=space.capacity,
        floorLevel=space.floor_level,
        layoutOptions=space.layout_options or [],
        sortOrder=space.sort_order,
        pricing=[],
        photos=[],
    )


def update_venue_space_mutation(id: str, spaceIn: VenueSpaceUpdateInputGQL, info: Info) -> VenueSpaceType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    space = crud_space.get(db, id=id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    venue = crud_venue_obj.get(db, id=space.venue_id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    obj_in = {}
    if spaceIn.name is not None:
        obj_in["name"] = spaceIn.name
    if spaceIn.description is not None:
        obj_in["description"] = spaceIn.description
    if spaceIn.capacity is not None:
        obj_in["capacity"] = spaceIn.capacity
    if spaceIn.floorLevel is not None:
        obj_in["floor_level"] = spaceIn.floorLevel
    if spaceIn.layoutOptions is not None:
        obj_in["layout_options"] = spaceIn.layoutOptions
    if spaceIn.sortOrder is not None:
        obj_in["sort_order"] = spaceIn.sortOrder

    updated = crud_space.update(db, db_obj=space, obj_in=obj_in)
    return VenueSpaceType(
        id=updated.id,
        venueId=updated.venue_id,
        name=updated.name,
        description=updated.description,
        capacity=updated.capacity,
        floorLevel=updated.floor_level,
        layoutOptions=updated.layout_options or [],
        sortOrder=updated.sort_order,
        pricing=[],
        photos=[],
    )


def delete_venue_space_mutation(id: str, info: Info) -> bool:
    user, org_id = _get_user_org(info)
    db = info.context.db
    space = crud_space.get(db, id=id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    venue = crud_venue_obj.get(db, id=space.venue_id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return crud_space.delete(db, id=id)


# --- Pricing ---

def set_space_pricing_mutation(
    spaceId: str, pricing: List[SpacePricingInputGQL], info: Info
) -> List[VenueSpacePricingType]:
    user, org_id = _get_user_org(info)
    db = info.context.db
    space = crud_space.get(db, id=spaceId)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    venue = crud_venue_obj.get(db, id=space.venue_id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    pricing_items = [
        {"rate_type": p.rateType, "amount": p.amount, "currency": p.currency}
        for p in pricing
    ]
    result = crud_space.set_pricing(db, space_id=spaceId, pricing_items=pricing_items)
    return [
        VenueSpacePricingType(
            id=p.id,
            spaceId=p.space_id,
            rateType=p.rate_type,
            amount=float(p.amount),
            currency=p.currency,
        )
        for p in result
    ]


# --- Amenities ---

def set_venue_amenities_mutation(
    venueId: str, amenities: List[VenueAmenityInputGQL], info: Info
) -> List[VenueAmenityType]:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=venueId)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")

    amenity_items = [
        {"amenity_id": a.amenityId, "metadata": a.metadata}
        for a in amenities
    ]
    result = crud_amenity_obj.set_venue_amenities(
        db, venue_id=venueId, amenity_items=amenity_items
    )
    return [
        VenueAmenityType(
            amenityId=r["amenity_id"],
            name=r["name"],
            categoryName=r["category_name"],
            categoryIcon=r["category_icon"],
            metadata=r["metadata"],
        )
        for r in result
    ]


# --- Photos (metadata only — upload via REST) ---

def update_venue_photo_mutation(
    id: str,
    info: Info,
    category: Optional[str] = None,
    caption: Optional[str] = None,
    sortOrder: Optional[int] = None,
    isCover: Optional[bool] = None,
) -> VenuePhotoType:
    user, org_id = _get_user_org(info)
    db = info.context.db
    photo = crud_photo.get(db, id=id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    venue = crud_venue_obj.get(db, id=photo.venue_id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    obj_in = {}
    if category is not None:
        obj_in["category"] = category
    if caption is not None:
        obj_in["caption"] = caption
    if sortOrder is not None:
        obj_in["sort_order"] = sortOrder
    if isCover is not None:
        obj_in["is_cover"] = isCover

    updated = crud_photo.update(db, db_obj=photo, obj_in=obj_in)
    return VenuePhotoType(
        id=updated.id,
        venueId=updated.venue_id,
        spaceId=updated.space_id,
        url=updated.url,
        category=updated.category,
        caption=updated.caption,
        sortOrder=updated.sort_order,
        isCover=updated.is_cover,
        createdAt=updated.created_at,
    )


def delete_venue_photo_mutation(id: str, info: Info) -> bool:
    user, org_id = _get_user_org(info)
    db = info.context.db
    photo = crud_photo.get(db, id=id)
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    venue = crud_venue_obj.get(db, id=photo.venue_id)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    s3_key = crud_photo.delete(db, id=id)
    if s3_key:
        try:
            from ..core.s3 import get_s3_client
            from ..core.config import settings
            s3_client = get_s3_client()
            s3_client.delete_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=s3_key)
        except Exception:
            pass
    return True


def reorder_venue_photos_mutation(
    venueId: str, photoIds: List[str], info: Info
) -> List[VenuePhotoType]:
    user, org_id = _get_user_org(info)
    db = info.context.db
    venue = crud_venue_obj.get(db, id=venueId)
    if not venue or venue.organization_id != org_id:
        raise HTTPException(status_code=404, detail="Venue not found")

    photos = crud_photo.reorder(db, venue_id=venueId, photo_ids=photoIds)
    return [
        VenuePhotoType(
            id=p.id,
            venueId=p.venue_id,
            spaceId=p.space_id,
            url=p.url,
            category=p.category,
            caption=p.caption,
            sortOrder=p.sort_order,
            isCover=p.is_cover,
            createdAt=p.created_at,
        )
        for p in photos
    ]


# --- Admin ---

def approve_venue_mutation(id: str, info: Info) -> VenueFullType:
    _require_admin(info)
    db = info.context.db
    try:
        venue = crud_venue_obj.approve(db, venue_id=id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return _venue_model_to_gql(venue)


def reject_venue_mutation(id: str, reason: str, info: Info) -> VenueFullType:
    _require_admin(info)
    db = info.context.db
    try:
        venue = crud_venue_obj.reject(db, venue_id=id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return _venue_model_to_gql(venue)


def suspend_venue_mutation(id: str, reason: str, info: Info) -> VenueFullType:
    _require_admin(info)
    db = info.context.db
    try:
        venue = crud_venue_obj.suspend(db, venue_id=id, reason=reason)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return _venue_model_to_gql(venue)

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class BlueprintBase(BaseModel):
    name: str = Field(..., example="Annual Sales Kick-off")
    description: Optional[str] = Field(
        None, example="Standard template for our yearly sales event."
    )
    template: Dict[str, Any] = Field(
        ..., example={"description": "Default description", "is_public": False}
    )


class BlueprintCreate(BlueprintBase):
    pass


class BlueprintUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    template: Optional[Dict[str, Any]] = None


class EventBlueprint(BlueprintBase):
    id: str
    organization_id: str
    is_archived: bool

    model_config = {"from_attributes": True}


class InstantiateBlueprintRequest(BaseModel):
    name: str = Field(..., description="The name for the new event.")
    start_date: datetime = Field(..., description="The start date for the new event.")
    end_date: datetime = Field(..., description="The end date for the new event.")

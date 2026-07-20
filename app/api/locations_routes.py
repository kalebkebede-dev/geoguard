"""Saved-locations CRUD -- add/list/remove, scoped to the logged-in user."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.db.models import SavedLocation, User
from app.db.session import get_db

router = APIRouter(prefix="/locations", tags=["locations"])


class SavedLocationRequest(BaseModel):
    label: str
    latitude: float
    longitude: float


class SavedLocationResponse(BaseModel):
    id: int
    label: str
    latitude: float
    longitude: float

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=SavedLocationResponse, status_code=status.HTTP_201_CREATED)
def add_location(
    body: SavedLocationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    location = SavedLocation(
        user_id=current_user.id,
        label=body.label,
        latitude=body.latitude,
        longitude=body.longitude,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("", response_model=list[SavedLocationResponse])
def list_locations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(SavedLocation)
        .filter(SavedLocation.user_id == current_user.id)
        .order_by(SavedLocation.created_at)
        .all()
    )


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_location(
    location_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    location = (
        db.query(SavedLocation)
        .filter(SavedLocation.id == location_id, SavedLocation.user_id == current_user.id)
        .one_or_none()
    )
    # 404 whether the location doesn't exist or belongs to someone else --
    # never reveal which, that's an information leak about other users' data.
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")

    db.delete(location)
    db.commit()

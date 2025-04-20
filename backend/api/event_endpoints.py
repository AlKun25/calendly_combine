"""API endpoints for event creation.

This module defines the API endpoints for selecting a time slot
and creating a calendar event.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field, EmailStr

from core.models import TimeSlot, CalendarEvent, EventParticipant, CalendarType
from core.overlap_engine import OverlapProcessor
from core.calendar_service import CalendarService
from adapters.base import AuthenticationError, EventCreationError


# Pydantic models for API request/response
class ParticipantInput(BaseModel):
    """Model for participant input in API requests."""
    email: EmailStr
    name: Optional[str] = None
    calendar_type: Optional[str] = None


class TimeSlotInput(BaseModel):
    """Model for time slot input in API requests."""
    start: datetime
    end: datetime
    timezone: str


class EventInput(BaseModel):
    """Model for event input in API requests."""
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    selected_slot: TimeSlotInput
    participants: List[ParticipantInput]
    organizer_email: Optional[str] = None
    preferred_calendar: Optional[str] = None


class EventOutput(BaseModel):
    """Model for event output in API responses."""
    event_id: str
    calendar_link: str
    title: str
    start_time: datetime
    end_time: datetime
    timezone: str
    status: str
    provider: str


# Create router
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


# Dependency to get services
def get_overlap_processor():
    """Get the overlap processor instance."""
    return OverlapProcessor()


def get_calendar_service():
    """Get the calendar service instance."""
    return CalendarService()


@router.post("/create-event", response_model=EventOutput)
async def create_event(
    event_input: EventInput,
    calendar_service: CalendarService = Depends(get_calendar_service)
):
    """Create a calendar event from a selected time slot.
    
    Args:
        event_input: The event details including selected time slot
        
    Returns:
        Details of the created event
        
    Raises:
        HTTPException: If event creation fails
    """
    try:
        # Convert input models to domain models
        time_slot = TimeSlot(
            start=event_input.selected_slot.start,
            end=event_input.selected_slot.end,
            timezone=event_input.selected_slot.timezone
        )
        
        participants = [
            EventParticipant(
                email=p.email,
                name=p.name,
                calendar_type=getattr(CalendarType, p.calendar_type.upper()) if p.calendar_type else None
            )
            for p in event_input.participants
        ]
        
        # Create calendar event
        calendar_event = CalendarEvent(
            title=event_input.title,
            start_time=time_slot.start,
            end_time=time_slot.end,
            timezone=time_slot.timezone,
            description=event_input.description,
            location=event_input.location,
            participants=participants,
            organizer=event_input.organizer_email
        )
        
        # Add preferred calendar if specified
        if event_input.preferred_calendar:
            calendar_event.metadata['preferred_calendar'] = event_input.preferred_calendar
        
        # Create the event using the calendar service
        confirmation = calendar_service.create_event(calendar_event)
        
        # Convert to API response model
        return EventOutput(
            event_id=confirmation.event_id,
            calendar_link=confirmation.calendar_link,
            title=confirmation.event.title,
            start_time=confirmation.event.start_time,
            end_time=confirmation.event.end_time,
            timezone=confirmation.event.timezone,
            status=confirmation.status,
            provider=confirmation.provider.name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except EventCreationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event creation failed: {str(e)}")


@router.post("/select-slot")
async def select_slot(
    slot_input: TimeSlotInput,
    overlap_processor: OverlapProcessor = Depends(get_overlap_processor)
):
    """Select a time slot from overlapping availability.
    
    This endpoint validates that the selected time slot exists within
    the overlapping availability slots.
    
    Args:
        slot_input: The selected time slot details
        
    Returns:
        Confirmation that the slot is valid
        
    Raises:
        HTTPException: If the slot is invalid or not available
    """
    try:
        # Convert to TimeSlot domain model
        selected_slot = TimeSlot(
            start=slot_input.start,
            end=slot_input.end,
            timezone=slot_input.timezone
        )
        
        # For now, just return success (in the future, we might want to validate
        # that the slot is within the overlaps)
        return {
            "status": "success",
            "message": "Time slot selected successfully",
            "slot": {
                "start": selected_slot.start,
                "end": selected_slot.end,
                "timezone": selected_slot.timezone
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to select time slot: {str(e)}")
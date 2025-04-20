"""API endpoints for event creation.

This module defines the API endpoints for selecting a time slot
and creating Google Calendar events.
"""

from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel, Field, EmailStr

from core.models import TimeSlot, CalendarEvent, EventParticipant, CalendarType
from core.calendar_service import CalendarService
from adapters.base import AuthenticationError, EventCreationError


# Pydantic models for API request/response
class ParticipantInput(BaseModel):
    """Model for participant input in API requests."""
    email: EmailStr
    name: Optional[str] = None


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


class EventOutput(BaseModel):
    """Model for event output in API responses."""
    event_id: str
    calendar_link: str
    title: str
    start_time: datetime
    end_time: datetime
    timezone: str
    status: str
    attendees: List[str]


# Create router
router = APIRouter(prefix="/api/calendar", tags=["calendar"])


# Dependency to get services
def get_calendar_service():
    """Get the calendar service instance."""
    return CalendarService()


@router.post("/create-event", response_model=EventOutput)
async def create_event(
    event_input: EventInput,
    calendar_service: CalendarService = Depends(get_calendar_service)
):
    """Create a Google Calendar event from a selected time slot.
    
    This endpoint creates a calendar event with the specified details
    and sends invites to all participants.
    
    Args:
        event_input: The event details including selected time slot
        calendar_service: Service for creating calendar events
        
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
        
        # Convert participant inputs to domain model
        participants = [
            EventParticipant(
                email=p.email,
                name=p.name,
                calendar_type=CalendarType.GOOGLE  # Force Google Calendar for event creation
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
        
        # Set preferred calendar to Google Calendar
        calendar_event.metadata['preferred_calendar'] = 'GOOGLE'
        
        # Create the event using the calendar service
        confirmation = calendar_service.create_event(calendar_event)
        
        # Construct attendee list
        attendees = [p.email for p in participants]
        
        # Convert to API response model
        return EventOutput(
            event_id=confirmation.event_id,
            calendar_link=confirmation.calendar_link,
            title=confirmation.event.title,
            start_time=confirmation.event.start_time,
            end_time=confirmation.event.end_time,
            timezone=confirmation.event.timezone,
            status=confirmation.status,
            attendees=attendees
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except EventCreationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Event creation failed: {str(e)}")
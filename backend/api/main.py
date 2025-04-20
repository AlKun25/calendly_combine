"""Main API application for Calendar Integrator.

This module defines the FastAPI application and endpoints for the Calendar Integrator.
It processes calendar links to find overlapping availability slots and allows
creating calendar events.
"""

import logging
from typing import List, Dict, Optional
from enum import Enum
from datetime import datetime
import pytz

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, HttpUrl

from core.models import CalendarType, TimeSlot
from core.overlap_engine import OverlapProcessor
from adapters.calendly import CalendlyAdapter
from adapters.google_calendar import GoogleCalendarAdapter
from api.event_endpoints import router as event_router


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "message": %(message)s}',
    datefmt="%Y-%m-%dT%H:%M:%S%z"
)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Calendar Integrator API",
    description="API for integrating multiple calendar availability links",
    version="1.0.0"
)


# Pydantic models for API input/output
class CalendarLinkType(str, Enum):
    """Enum for calendar link types in the API."""
    CALENDLY = "calendly"
    GOOGLE = "google"


class CalendarLink(BaseModel):
    """Model for a calendar link input."""
    url: HttpUrl
    type: CalendarLinkType
    owner_email: Optional[str] = None
    owner_name: Optional[str] = None


class CalendarLinkInput(BaseModel):
    """Model for calendar links input."""
    links: List[CalendarLink]
    meeting_name: str = "Availability Meeting"
    meeting_duration_minutes: Optional[int] = 30


class TimeSlotOutput(BaseModel):
    """Model for a time slot in the output."""
    start: datetime
    end: datetime
    timezone: str


class OverlapResponse(BaseModel):
    """Model for the API overlap response."""
    slots: int
    overlapping_slots: List[TimeSlotOutput]
    participants: List[Dict[str, str]]


# Dependency to get services
def get_overlap_processor():
    """Get the overlap processor instance."""
    return OverlapProcessor()


def get_calendly_adapter():
    """Get a Calendly adapter instance."""
    return CalendlyAdapter(mock_mode=False)


def get_google_calendar_adapter():
    """Get a Google Calendar adapter instance."""
    return GoogleCalendarAdapter()


# API routes
@app.post("/api/calendar/process", response_model=OverlapResponse)
async def process_calendar_links(
    input_data: CalendarLinkInput,
    overlap_processor: OverlapProcessor = Depends(get_overlap_processor),
    calendly_adapter: CalendlyAdapter = Depends(get_calendly_adapter),
    google_adapter: GoogleCalendarAdapter = Depends(get_google_calendar_adapter)
):
    """Process multiple calendar links to find overlapping availability.
    
    This endpoint extracts availability from the provided calendar links
    and finds the overlapping time slots.
    
    Args:
        input_data: Input data with calendar links
        overlap_processor: Dependency for processing overlaps
        calendly_adapter: Dependency for processing Calendly links
        google_adapter: Dependency for processing Google Calendar links
        
    Returns:
        Overlapping time slots and participant information
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        logger.info(f"Processing {len(input_data.links)} calendar links")
        
        # Collect availability schedules from each link
        availability_schedules = []
        participants = []
        
        for link_data in input_data.links:
            try:
                # Select appropriate adapter based on link type
                if link_data.type == CalendarLinkType.CALENDLY:
                    adapter = calendly_adapter
                elif link_data.type == CalendarLinkType.GOOGLE:
                    adapter = google_adapter
                else:
                    raise ValueError(f"Unsupported calendar type: {link_data.type}")
                
                # Extract availability
                schedule = adapter.extract_availability(str(link_data.url))
                availability_schedules.append(schedule)
                
                # Add participant info
                participant = {
                    "email": link_data.owner_email or schedule.owner_name or "unknown",
                    "name": link_data.owner_name or schedule.owner_name or "Unknown",
                    "calendar_type": link_data.type
                }
                participants.append(participant)
                
                logger.info(f"Extracted {len(schedule.time_slots)} slots from {link_data.url}")
                
            except Exception as e:
                logger.error(f"Error processing link {link_data.url}: {e}")
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to process calendar link {link_data.url}: {str(e)}"
                )
        
        # Find overlapping slots
        overlap_slots = overlap_processor.find_overlapping_slots(availability_schedules)
        logger.info(f"Found {len(overlap_slots)} overlapping time slots")
        
        # Apply duration filter if specified
        if input_data.meeting_duration_minutes:
            duration_minutes = input_data.meeting_duration_minutes
            # Filter slots that are long enough for the meeting
            filtered_slots = []
            for slot in overlap_slots:
                duration = (slot.end - slot.start).total_seconds() / 60
                if duration >= duration_minutes:
                    filtered_slots.append(slot)
            
            overlap_slots = filtered_slots
            logger.info(f"Filtered to {len(overlap_slots)} slots with duration >= {duration_minutes} minutes")
        
        # Convert to response format
        overlap_output = [
            TimeSlotOutput(
                start=slot.start,
                end=slot.end,
                timezone=slot.timezone
            ) for slot in overlap_slots
        ]
        
        # Return the response
        return OverlapResponse(
            slots=len(overlap_slots),
            overlapping_slots=overlap_output,
            participants=participants
        )
    
    except Exception as e:
        logger.error(f"Error processing calendar links: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process calendar links: {str(e)}"
        )


# Include event router
app.include_router(event_router)
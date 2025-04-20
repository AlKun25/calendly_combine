"""Main API application for Calendar Integrator.

This module defines the FastAPI application and endpoints for the Calendar Integrator.
"""

import logging
from typing import List, Dict, Optional
from enum import Enum

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, HttpUrl

from core.models import CalendarType, TimeSlot
from core.overlap_engine import OverlapProcessor
from adapters.calendly import CalendlyAdapter
from adapters.google_calendar import GoogleCalendarAdapter
from adapters.output.link_generator import OutputFormat, OutputLinkGenerator
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


class OutputFormatType(str, Enum):
    """Enum for output format types in the API."""
    CALENDLY = "calendly"
    LETTUCEMEET = "lettucemeet"
    GOOGLE = "google"


class CalendarLink(BaseModel):
    """Model for a calendar link input."""
    url: HttpUrl
    type: CalendarLinkType


class CalendarLinkInput(BaseModel):
    """Model for calendar links input."""
    links: List[CalendarLink]
    output_format: OutputFormatType = OutputFormatType.CALENDLY
    meeting_name: str = "Availability Meeting"


class TimeSlotOutput(BaseModel):
    """Model for a time slot in the output."""
    start: str
    end: str
    timezone: str


class OutputResponse(BaseModel):
    """Model for the API response."""
    link: str
    slots: int
    overlapping_slots: List[TimeSlotOutput]


# API routes
@app.post("/api/calendar/process", response_model=OutputResponse)
async def process_calendar_links(input_data: CalendarLinkInput):
    """Process multiple calendar links to find overlapping availability."""
    # TODO: Implement calendar link processing
    pass

app.include_router(event_router)
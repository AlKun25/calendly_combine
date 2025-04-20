"""Domain models for Calendar Integrator.

This module contains the core domain models for the Calendar Integrator application.
These models represent the fundamental data structures and business logic for
processing calendar availability.
"""

from __future__ import annotations
from enum import Enum, auto
from dataclasses import dataclass, field # * different from pydantic dataclass
from datetime import datetime, timezone
from typing import Set, Optional
import pytz
import logging

# Configure module logger
logger = logging.getLogger(__name__)

class CalendarType(Enum):
    """Enumeration of supported calendar types."""
    CALENDLY = auto()
    GOOGLE = auto()

# TODO: Add variables to store UTC values at initialization, save on compute costs later
@dataclass(frozen=True)
class TimeSlot:
    """Represents a time slot with start and end times in a specific timezone."""
    start: datetime
    end: datetime
    timezone: str
    
    def __post_init__(self):
        """Validate the time slot upon initialization.
        
        Raises:
            ValueError: If start time is not before end time or timezone is invalid.
        """
        # We need to use object.__setattr__ because the dataclass is frozen
        if self.start >= self.end:
            raise ValueError("Start time must be before end time")
        
        # Validate timezone
        try:
            pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {self.timezone}")
    
    def to_utc(self) -> 'TimeSlot':
        """Convert the time slot to UTC timezone.
        
        Returns:
            A new TimeSlot object with times converted to UTC.
        """
        # Get the timezone object
        tz = pytz.timezone(self.timezone)
        
        # Ensure start time is timezone-aware
        if self.start.tzinfo is None:
            start_aware = tz.localize(self.start)
        else:
            start_aware = self.start
        
        # Convert to UTC
        start_utc = start_aware.astimezone(timezone.utc)
        
        # Ensure end time is timezone-aware
        if self.end.tzinfo is None:
            end_aware = tz.localize(self.end)
        else:
            end_aware = self.end
        
        # Convert to UTC
        end_utc = end_aware.astimezone(timezone.utc)
        
        return TimeSlot(
            start=start_utc,
            end=end_utc,
            timezone='UTC'
        )
    
    def overlaps_with(self, other: 'TimeSlot'):
        """Check if this time slot overlaps with another.
        
        Args:
            other: Another TimeSlot to check for overlap with.
            
        Returns:
            True if the slots overlap, False otherwise.
        """
        # Quick check - if timezones are the same, we can avoid conversions
        if self.timezone == other.timezone:
            return (self.start < other.end and self.end > other.start)
        
        # For different timezones, convert both to UTC
        self_utc = self.to_utc()
        other_utc = other.to_utc()
        
        return (self_utc.start < other_utc.end and self_utc.end > other_utc.start)

    def get_overlap(self, other: 'TimeSlot'):
        """Get the overlapping portion of this slot with another.
        
        Args:
            other: Another TimeSlot to find overlap with.
            
        Returns:
            A new TimeSlot representing the overlap, or None if no overlap.
        """
        if not self.overlaps_with(other):
            return None
        
        # Convert both to UTC for consistent comparison
        self_utc = self.to_utc()
        other_utc = other.to_utc()
        
        # Find overlap boundaries
        overlap_start = max(self_utc.start, other_utc.start)
        overlap_end = min(self_utc.end, other_utc.end)
        
        return TimeSlot(
            start=overlap_start,
            end=overlap_end,
            timezone='UTC'  # Return in UTC
        )


@dataclass
class AvailabilitySchedule:
    """Represents a collection of available time slots for a calendar.
    
    Attributes:
        calendar_id: Unique identifier for the calendar.
        calendar_type: Type of calendar (Calendly, Google, etc.).
        time_slots: Set of available time slots.
        owner_name: Optional name of the calendar owner.
    """
    calendar_id: str
    calendar_type: CalendarType
    time_slots: Set[TimeSlot] = field(default_factory=set)
    owner_name: Optional[str] = None  #TODO: Add owner class to provide localization 
    
    def add_slot(self, slot: TimeSlot) -> None:
        """Add a time slot to this schedule.
        
        Args:
            slot: The TimeSlot to add.
        """
        self.time_slots.add(slot)
        logger.debug(
            f"Added slot: {slot.start.isoformat()} to {slot.end.isoformat()} "
            f"({slot.timezone}) to calendar {self.calendar_id}"
        )
    
    def get_utc_slots(self) -> Set[TimeSlot]:
        """Get all time slots converted to UTC timezone.
        
        Returns:
            A set of TimeSlot objects all in UTC timezone.
        """
        return {slot.to_utc() for slot in self.time_slots}

@dataclass
class EventParticipant:
    """Represents a participant for a calendar event.
    
    Attributes:
        email: Email address of the participant
        name: Optional name of the participant
        calendar_type: Type of calendar the participant uses
        response_status: Optional response status (accepted, declined, etc.)
    """
    email: str
    name: Optional[str] = None
    calendar_type: Optional[CalendarType] = None
    response_status: Optional[str] = None

    def __post_init__(self):
        """Validate participant data upon initialization."""
        if not self.email or '@' not in self.email:
            raise ValueError("Valid email is required for participant")


@dataclass
class CalendarEvent:
    """Represents a calendar event to be created.
    
    Attributes:
        title: Title/summary of the event
        start_time: Start time of the event
        end_time: End time of the event
        timezone: Timezone of the event
        description: Optional description of the event
        location: Optional location of the event
        participants: List of participants to invite
        organizer: Email of the event organizer
        metadata: Additional calendar-specific metadata
    """
    title: str
    start_time: datetime
    end_time: datetime
    timezone: str
    description: Optional[str] = None
    location: Optional[str] = None
    participants: List[EventParticipant] = field(default_factory=list)
    organizer: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate event data upon initialization."""
        if self.start_time >= self.end_time:
            raise ValueError("Start time must be before end time")
        
        # Validate timezone
        try:
            pytz.timezone(self.timezone)
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {self.timezone}")

    @classmethod
    def from_time_slot(cls, 
                       time_slot: TimeSlot, 
                       title: str, 
                       participants: List[EventParticipant],
                       description: Optional[str] = None,
                       organizer: Optional[str] = None,
                       location: Optional[str] = None) -> 'CalendarEvent':
        """Create a CalendarEvent from a TimeSlot.
        
        Args:
            time_slot: The TimeSlot to convert
            title: The title for the event
            participants: List of participants to invite
            description: Optional description for the event
            organizer: Optional email of the event organizer
            location: Optional location for the event
            
        Returns:
            A new CalendarEvent instance
        """
        return cls(
            title=title,
            start_time=time_slot.start,
            end_time=time_slot.end,
            timezone=time_slot.timezone,
            description=description,
            location=location,
            participants=participants,
            organizer=organizer
        )


@dataclass
class EventConfirmation:
    """Represents confirmation details for a created event.
    
    Attributes:
        event_id: ID of the created event
        calendar_link: Link to the event in the calendar
        event: The event details
        status: Status of the event creation
        provider: The calendar provider used
    """
    event_id: str
    calendar_link: str
    event: CalendarEvent
    status: str
    provider: CalendarType
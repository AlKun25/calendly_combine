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
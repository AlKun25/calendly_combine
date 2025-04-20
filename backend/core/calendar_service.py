"""Calendar service for event creation.

This module provides a service to orchestrate calendar event creation
using the appropriate adapters based on the calendar type.
"""

import logging
from typing import Dict, Optional

from core.models import CalendarEvent, EventConfirmation, CalendarType
from adapters.base import BaseAdapter, AuthenticationError, EventCreationError
from adapters.calendly import CalendlyAdapter
from adapters.google_calendar import GoogleCalendarAdapter

# Configure module logger
logger = logging.getLogger(__name__)


class CalendarService:
    """Service for creating calendar events.
    
    This service orchestrates the creation of calendar events using
    the appropriate adapter based on the calendar type.
    """
    
    def __init__(self, adapters: Optional[Dict[CalendarType, BaseAdapter]] = None):
        """Initialize the calendar service with available adapters.
        
        Args:
            adapters: Optional dictionary mapping calendar types to adapters
                     If not provided, default adapters will be initialized
        """
        # Use provided adapters or initialize defaults
        self.adapters = adapters or {
            CalendarType.GOOGLE: GoogleCalendarAdapter(),
            CalendarType.CALENDLY: CalendlyAdapter()
        }
    
    def create_event(self, event: CalendarEvent) -> EventConfirmation:
        """Create a calendar event.
        
        Args:
            event: The event to create
            
        Returns:
            Confirmation details for the created event
            
        Raises:
            ValueError: If no adapter is available for the event's calendar type
            AuthenticationError: If authentication fails
            EventCreationError: If event creation fails
        """
        # Determine which calendar to use for the event
        calendar_type = self._determine_calendar_type(event)
        
        if calendar_type not in self.adapters:
            raise ValueError(f"No adapter available for calendar type: {calendar_type}")
        
        adapter = self.adapters[calendar_type]
        
        if not adapter.is_authenticated():
            # Try to authenticate (this may prompt for credentials)
            try:
                adapter.authenticate()
            except AuthenticationError as e:
                raise AuthenticationError(f"Authentication failed: {str(e)}")
        
        try:
            logger.info(f"Creating event '{event.title}' using {calendar_type} calendar")
            return adapter.create_event(event)
        except EventCreationError as e:
            logger.error(f"Failed to create event: {e}")
            raise EventCreationError(f"Failed to create event: {str(e)}")
    
    def _determine_calendar_type(self, event: CalendarEvent) -> CalendarType:
        """Determine which calendar type to use for the event.
        
        Args:
            event: The event to create
            
        Returns:
            The determined calendar type to use
            
        Raises:
            ValueError: If calendar type cannot be determined
        """
        # If organizer has a specific calendar type preference in metadata
        if event.metadata and 'preferred_calendar' in event.metadata:
            preferred = event.metadata['preferred_calendar']
            if isinstance(preferred, CalendarType) and preferred in self.adapters:
                return preferred
            elif isinstance(preferred, str) and hasattr(CalendarType, preferred.upper()):
                calendar_type = getattr(CalendarType, preferred.upper())
                if calendar_type in self.adapters:
                    return calendar_type
        
        # If all participants use the same calendar type, use that
        if event.participants:
            calendar_types = [p.calendar_type for p in event.participants if p.calendar_type]
            if calendar_types and all(ct == calendar_types[0] for ct in calendar_types):
                if calendar_types[0] in self.adapters:
                    return calendar_types[0]
        
        # Default preference order if available
        preference_order = [CalendarType.GOOGLE, CalendarType.CALENDLY]
        for calendar_type in preference_order:
            if calendar_type in self.adapters:
                return calendar_type
        
        # Fallback to the first available adapter
        if self.adapters:
            return next(iter(self.adapters.keys()))
        
        raise ValueError("No calendar adapter available")
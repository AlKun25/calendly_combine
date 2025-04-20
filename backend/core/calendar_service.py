"""Calendar service for event creation.

This module provides a service to orchestrate calendar event creation
using Google Calendar as the primary provider.
"""

import logging
from typing import Dict, Optional

from core.models import CalendarEvent, EventConfirmation, CalendarType
from adapters.base import BaseAdapter, AuthenticationError, EventCreationError
from adapters.google_calendar import GoogleCalendarAdapter

# Configure module logger
logger = logging.getLogger(__name__)


class CalendarService:
    """Service for creating calendar events.
    
    This service orchestrates the creation of calendar events primarily
    using Google Calendar as the provider.
    """
    
    def __init__(self, google_adapter: Optional[GoogleCalendarAdapter] = None):
        """Initialize the calendar service with Google Calendar adapter.
        
        Args:
            google_adapter: Optional Google Calendar adapter
                          If not provided, a default one will be initialized
        """
        # Use provided adapter or initialize default
        self.google_adapter = google_adapter or GoogleCalendarAdapter()
    
    def create_event(self, event: CalendarEvent) -> EventConfirmation:
        """Create a calendar event using Google Calendar.
        
        Args:
            event: The event to create
            
        Returns:
            Confirmation details for the created event
            
        Raises:
            AuthenticationError: If authentication fails
            EventCreationError: If event creation fails
        """
        # Ensure we're authenticated with Google Calendar
        if not self.google_adapter.is_authenticated():
            # Try to authenticate (this may prompt for credentials)
            try:
                self.google_adapter.authenticate()
            except AuthenticationError as e:
                logger.error(f"Google Calendar authentication failed: {e}")
                raise AuthenticationError(f"Google Calendar authentication failed: {str(e)}")
        
        try:
            logger.info(f"Creating event '{event.title}' in Google Calendar")
            return self.google_adapter.create_event(event)
        except EventCreationError as e:
            logger.error(f"Failed to create event: {e}")
            raise EventCreationError(f"Failed to create event: {str(e)}")
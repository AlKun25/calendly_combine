"""Calendar service for event creation.

This module provides a service to orchestrate calendar event creation
using Google Calendar as the primary provider.
"""

import logging
from typing import Dict, Optional

# Import Credentials for type hinting
from google.oauth2.credentials import Credentials 

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
    
    def create_event(
        self, 
        event: CalendarEvent, 
        google_credentials: Optional[Credentials] = None
    ) -> EventConfirmation:
        """Create a calendar event using Google Calendar.
        
        Args:
            event: The event to create
            google_credentials: The authenticated Google OAuth Credentials object.
            
        Returns:
            Confirmation details for the created event
            
        Raises:
            AuthenticationError: If authentication credentials are missing or invalid.
            EventCreationError: If event creation fails.
        """
        # Remove internal authentication check; expect valid credentials to be passed
        # if not self.google_adapter.is_authenticated():
        #     try:
        #         self.google_adapter.authenticate()
        #     except AuthenticationError as e:
        #         logger.error(f"Google Calendar authentication failed: {e}")
        #         raise AuthenticationError(f"Google Calendar authentication failed: {str(e)}")

        if not google_credentials:
             raise AuthenticationError("Google credentials are required for event creation.")

        try:
            logger.info(f"Creating event '{event.title}' in Google Calendar")
            # Pass the credentials to the adapter's create_event method
            return self.google_adapter.create_event(event, credentials=google_credentials)
        except AuthenticationError as e: # Catch potential auth errors from adapter
             logger.error(f"Google Calendar authentication failed during event creation: {e}")
             raise
        except EventCreationError as e:
            logger.error(f"Failed to create event: {e}")
            raise # Re-raise the specific error
"""Base adapter interface for external services.

This module defines the base adapter interface for interacting with 
external calendar services. It provides a common structure for all adapters
to implement authentication, availability extraction, and event creation.
"""

import abc
import logging
from typing import Dict, List, Any, Optional

from core.models import AvailabilitySchedule, CalendarEvent, EventConfirmation

# Configure module logger
logger = logging.getLogger(__name__)


class BaseAdapterError(Exception):
    """Base exception for all adapter errors."""
    pass


class AuthenticationError(BaseAdapterError):
    """Exception raised when authentication with a service fails."""
    pass


class ResourceNotFoundError(BaseAdapterError):
    """Exception raised when a requested resource is not found."""
    pass


class EventCreationError(BaseAdapterError):
    """Exception raised when event creation fails."""
    pass


class BaseAdapter(abc.ABC):
    """Base class for all external service adapters.
    
    This abstract class defines the common interface that all
    calendar service adapters must implement.
    """
    
    @abc.abstractmethod
    def authenticate(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """Authenticate with the external service.
        
        Args:
            credentials: Optional credentials dict for authentication
            
        Returns:
            True if authentication was successful
            
        Raises:
            AuthenticationError: If authentication fails
        """
        pass
    
    @abc.abstractmethod
    def is_authenticated(self) -> bool:
        """Check if authenticated with the external service.
        
        Returns:
            True if authenticated, False otherwise
        """
        pass
    
    @abc.abstractmethod
    def extract_availability(self, link: str) -> AvailabilitySchedule:
        """Extract availability information from a calendar link.
        
        Args:
            link: The calendar link to extract availability from
            
        Returns:
            An AvailabilitySchedule object with available time slots
            
        Raises:
            ValueError: If the link format is invalid
            AuthenticationError: If authentication fails
            ResourceNotFoundError: If the resource is not found
            BaseAdapterError: For other service-specific errors
        """
        pass
    
    @abc.abstractmethod
    def create_event(self, event: CalendarEvent) -> EventConfirmation:
        """Create a calendar event.
        
        Args:
            event: The event to create
            
        Returns:
            Confirmation details for the created event
            
        Raises:
            AuthenticationError: If not authenticated
            EventCreationError: If event creation fails
        """
        pass
"""Calendly adapter for extracting availability information.

This module provides functionality to extract availability information from
Calendly links using the Calendly API v2.
"""

import re
import logging
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone

import httpx
from dotenv import load_dotenv

from core.models import AvailabilitySchedule, TimeSlot, CalendarType


# Configure module logger
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


class CalendlyAdapter:
    """Adapter for extracting availability information from Calendly links.
    
    This adapter uses Calendly's API v2 to extract availability information
    from a Calendly user or event type link.
    """
    
    # Regex pattern to extract user name or UUID from Calendly links
    USER_PATTERN = r'calendly\.com/([^/]+)(?:/([^/]+))?'
    
    # Calendly API base URL
    API_BASE_URL = "https://api.calendly.com"
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Calendly adapter.
        
        Args:
            api_key: Optional Calendly API key for authenticated requests.
                    If not provided, will attempt to use environment variables.
        """
        self.api_key = api_key or os.getenv("CALENDLY_API_KEY")
        if not self.api_key:
            logger.warning("No Calendly API key provided or found in environment")
            raise ValueError("Calendly API key is required")
        
        # Create HTTP client with appropriate timeout
        self.http_client = httpx.Client(timeout=10.0)
        
        # Set up authorization headers if API key is available
        if self.api_key:
            self.http_client.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            })
    
    def extract_availability(self, calendly_link: str) -> AvailabilitySchedule:
        """Extract availability information from a Calendly link.
        
        This method accepts a Calendly user or event type link and extracts
        the available time slots by querying the Calendly API.
        
        Args:
            calendly_link: The Calendly link to extract availability from.
            
        Returns:
            An AvailabilitySchedule object with the extracted time slots.
            
        Raises:
            ValueError: If the Calendly link format is invalid.
            httpx.HTTPError: If there's an error communicating with the Calendly API.
        """
        logger.info(f"Extracting availability from Calendly link: {calendly_link}")
        
        # Extract user and event type information from the link
        user_name, event_type = self._extract_user_info(calendly_link)
        
        if not user_name:
            raise ValueError(f"Invalid Calendly link format: {calendly_link}")
        
        try:
            # Get user UUID from username
            user_data = self._get_user_data(user_name)
            user_uri = user_data.get("resource", {}).get("uri")
            
            if not user_uri:
                raise ValueError(f"Could not find user with name: {user_name}")
            
            # Create availability schedule
            schedule = AvailabilitySchedule(
                calendar_id=user_uri,
                calendar_type=CalendarType.CALENDLY,
                owner_name=user_data.get("resource", {}).get("name")
            )
            
            # Get available time slots
            available_slots = self._get_available_slots(user_uri, event_type)
            
            # Add slots to schedule
            for slot in available_slots:
                schedule.add_slot(slot)
            
            logger.info(
                f"Successfully extracted {len(schedule.time_slots)} available time slots"
            )
            return schedule
            
        except httpx.HTTPError as e:
            logger.error(f"HTTP error during Calendly API request: {e}")
            raise
        except Exception as e:
            logger.error(f"Error extracting availability from Calendly: {e}")
            raise
    
    def _extract_user_info(self, calendly_link: str) -> tuple[str, Optional[str]]:
        """Extract user name and event type from a Calendly link.
        
        Args:
            calendly_link: The Calendly link to extract information from.
            
        Returns:
            A tuple of (user_name, event_type) where event_type may be None.
        """
        match = re.search(self.USER_PATTERN, calendly_link)
        
        if not match:
            return "", None
            
        user_name = match.group(1)
        event_type = match.group(2) if match.groupdict() and len(match.groups()) > 1 else None
        
        logger.debug(f"Extracted user_name={user_name}, event_type={event_type}")
        return user_name, event_type
    
    def _get_user_data(self, user_name: str) -> Dict[str, Any]:
        """Get user data from the Calendly API.
        
        Args:
            user_name: The Calendly user name to look up.
            
        Returns:
            User data from the Calendly API.
            
        Raises:
            ValueError: If the user could not be found.
            httpx.HTTPError: If there's an error communicating with the Calendly API.
        """
        if not self.api_key:
            logger.warning("No API key available for user data lookup")
            # Return minimal mock data for development
            return {
                "resource": {
                    "uri": f"https://api.calendly.com/users/{user_name}",
                    "name": user_name.capitalize()
                }
            }
        
        logger.debug(f"Looking up user data for {user_name}")
        
        # In a real implementation, we would need to list users and find by name
        # For this MVP, we'll mock this with a direct call assuming username = UUID
        url = f"{self.API_BASE_URL}/users/{user_name}"
        
        response = self.http_client.get(url)
        response.raise_for_status()
        
        return response.json()
    
    def _get_available_slots(
        self, user_uri: str, event_type: Optional[str] = None
    ) -> List[TimeSlot]:
        """Get available time slots for a user.
        
        This method retrieves the available time slots for a given user,
        optionally filtered by event type.
        
        Args:
            user_uri: The Calendly user URI.
            event_type: Optional event type to filter by.
            
        Returns:
            List of TimeSlot objects representing available times.
        """
        logger.debug(f"Getting available slots for {user_uri}, event_type={event_type}")
        
        if self.api_key:
            # In a full implementation, we would:
            # 1. Get the user's availability schedule
            # 2. Get the user's busy times
            # 3. Calculate available slots based on schedule minus busy times
            # 4. If event_type is provided, get that event type's constraints
            
            # For this MVP, we'll use a simpler approach and mock the data
            pass
        
        # For the MVP, we'll mock some time slots
        slots = []
        
        # Get current date/time
        now = datetime.now(timezone.utc)
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Create example time slots for the next 7 days
        for day_offset in range(7):
            day = today + timedelta(days=day_offset)
            
            # Add business hours slots (9AM-5PM)
            for hour in range(9, 17):
                # Skip weekend slots
                weekday = day.weekday()
                if weekday >= 5:  # 5 = Saturday, 6 = Sunday
                    continue
                
                # Create a 30-minute slot
                start_time = day.replace(hour=hour, minute=0)
                end_time = day.replace(hour=hour, minute=30)
                
                # Skip slots in the past
                if end_time <= now:
                    continue
                
                slots.append(TimeSlot(
                    start=start_time,
                    end=end_time,
                    timezone="UTC"
                ))
                
                # Add the second half-hour slot
                start_time = day.replace(hour=hour, minute=30)
                end_time = day.replace(hour=hour + 1, minute=0)
                
                # Skip slots in the past
                if end_time <= now:
                    continue
                
                slots.append(TimeSlot(
                    start=start_time,
                    end=end_time,
                    timezone="UTC"
                ))
        
        # Log the number of slots created
        logger.info(f"Created {len(slots)} mock time slots for {user_uri}")
        
        return slots